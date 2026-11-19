"""VASTU AI Studio: one-process Flask application, conceptual plans only."""
import io, os, re, json, math, base64, socket, urllib.request, urllib.error
from flask import Flask, request, jsonify, send_file, render_template
from werkzeug.utils import secure_filename
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# Load local secrets without exposing them in the browser or Git repository.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
app=Flask(__name__)
app.config['MAX_CONTENT_LENGTH']=15*1024*1024
ROOMS=['Living','Kitchen','Master Bedroom','Bedroom','Pooja','Bathroom','Toilet','Staircase','Parking','Dining','Store','Study']
PREF={'Living':['N','NE','E'],'Kitchen':['SE','NW'],'Master Bedroom':['SW'],'Bedroom':['W','NW','S'],'Pooja':['NE'],'Bathroom':['W','NW'],'Toilet':['W','NW'],'Staircase':['S','SW','W'],'Parking':['N','NW'],'Dining':['E','W'],'Store':['S','SW'],'Study':['N','NE','E']}
REMEDY={'Kitchen':'Prefer a southeast kitchen where feasible; avoid relocating plumbing without professional advice.','Pooja':'Prefer a northeast prayer space; a clean dedicated prayer corner is a non-structural option.','Master Bedroom':'Southwest is traditionally preferred; consider room reassignment if practical.','Toilet':'Traditionally northwest or west is preferred; keep ventilation and waterproofing adequate.','Staircase':'South, southwest or west is traditionally preferred; structural changes need engineering review.'}

def zone(x,y,w,h):
    cx=(x+w/2); cy=(y+h/2)
    hor='W' if cx<1/3 else 'E' if cx>2/3 else ''
    ver='N' if cy<1/3 else 'S' if cy>2/3 else ''
    return ver+hor if ver+hor else 'C'

def score_room(name,z):
    preferred=PREF.get(name,[])
    match=z in preferred or (len(z)==2 and any(z==a for a in preferred))
    score=100 if match else 65 if z=='C' else 45
    return {'name':name,'zone':z,'score':score,'preferred':', '.join(preferred),'advice':('Traditional placement aligns with preference.' if match else REMEDY.get(name,f'Traditional guidance prefers {", ".join(preferred)}; consider swapping room usage if practical.'))}

def make_floor(width,length,rooms,floor,facing):
    # Coordinate system: north at top, x east, y south. Central continuous hall connects all rooms.
    corridor=max(3.5,min(5.0,width*.17))
    side=(width-corridor)/2
    if side<5: raise ValueError('Plot width must be at least 14 ft for this corridor layout.')
    slots=max(1,math.ceil(len(rooms)/2))
    if length/slots<5: raise ValueError('Too many rooms for this plot; reduce rooms or increase plot length.')
    row=length/slots
    placed=[]
    for i,name in enumerate(rooms):
        r=i//2; left=i%2==0
        x=0 if left else side+corridor
        w=side; y=r*row; h=row
        z=zone(x/width,y/length,w/width,h/length)
        placed.append({'name':name,'x':round(x,3),'y':round(y,3),'w':round(w,3),'h':round(h,3),'side':'left' if left else 'right','zone':z})
    evaluations=[score_room(r['name'],r['zone']) for r in placed]
    return {'floor':floor,'width':width,'length':length,'facing':facing,'corridor':{'x':side,'w':corridor},'rooms':placed,'evaluations':evaluations,'score':round(sum(r['score'] for r in evaluations)/len(evaluations)) if evaluations else None,'notes':['Conceptual zoning, not a construction drawing.','Room doors open to the continuous central corridor.','External entrance is indicative; setbacks, windows, structure and building codes are not validated.']}

def valid_plan(body):
    width=float(body.get('width',25)); length=float(body.get('length',45)); floors=int(body.get('floors',0))
    if not (14<=width<=150 and 18<=length<=250 and 0<=floors<=15):raise ValueError('Width 14–150 ft, length 18–250 ft and floors G–G+15 required.')
    facing=str(body.get('facing','N')).upper()
    if facing not in ('N','S','E','W'):raise ValueError('Invalid facing.')
    raw=body.get('rooms',{})
    if not isinstance(raw,dict):raise ValueError('Rooms must be a dictionary.')
    rooms=[]
    for name in ROOMS:
        n=int(raw.get(name,0))
        if n<0 or n>12:raise ValueError('Each room count must be 0–12.')
        rooms += [name]*n
    if not rooms:raise ValueError('Choose at least one room.')
    return width,length,floors,facing,rooms

@app.get('/api/health')
def health():return jsonify(status='ok',version='4.0')

@app.post('/api/generate')
def generate():
    try:
        width,length,floors,facing,rooms=valid_plan(request.get_json(force=True))
        plans=[make_floor(width,length,rooms,i,facing) for i in range(floors+1)]
        return jsonify(plans=plans,disclaimer='Traditional Vastu guidance is not scientifically validated. Consult licensed professionals before construction.')
    except (ValueError,TypeError,OverflowError) as e:return jsonify(error=str(e)),400

@app.post('/api/evaluate')
def evaluate():
    body=request.get_json(force=True)
    entries=body.get('rooms',[])
    if not isinstance(entries,list) or len(entries)>100:return jsonify(error='Invalid rooms list'),400
    result=[]
    for item in entries:
        if not isinstance(item,dict) or item.get('name') not in ROOMS or item.get('zone') not in ('N','NE','E','SE','S','SW','W','NW','C'):
            return jsonify(error='Invalid room or direction'),400
        result.append(score_room(item['name'],item['zone']))
    return jsonify(score=round(sum(r['score'] for r in result)/len(result)) if result else None,evaluations=result,disclaimer='Advisory traditional Vastu score, not a safety or scientific rating.')

def gemini_http_error(status, raw, key):
    """Return actionable API errors without exposing API keys or request data."""
    try:
        obj=json.loads(raw)
        detail=str(obj.get('error',{}).get('message',''))
    except (ValueError,TypeError,AttributeError):
        detail=''
    detail=detail.replace(key,'[REDACTED]')
    detail=re.sub(r'AIza[\w-]{20,}', '[REDACTED]', detail)
    detail=re.sub(r'AQ\.[\w-]{15,}', '[REDACTED]', detail)
    detail=re.sub(r'https?://\S+', '[URL]', detail)
    if status==400:
        hint='Bad request: inspect model name, image payload and API parameters.'
    elif status==404:
        hint='Model/endpoint not found. Check GEMINI_MODEL and supported models.'
    elif status in (401,403):
        hint='API authentication or project access denied.'
    elif status==429:
        hint='Rate limit or quota reached; wait or review Google AI Studio usage.'
    else:
        hint='Check Gemini API configuration and service status.'
    return f'Gemini HTTP {status}: {detail[:350] or hint}'

def gemini_analyze(data, ext, north):
    """Best-effort AI observations; never infer a definitive geometry or score."""
    key=os.environ.get('GEMINI_API_KEY','').strip()
    if not key: return None, 'Gemini API key not configured. Add GEMINI_API_KEY to .env to enable AI review.'
    try:
        if ext=='.pdf':
            import fitz
            doc=fitz.open(stream=data,filetype='pdf')
            if not len(doc): return None,'PDF contains no pages.'
            # One page per request to limit free-tier use and protect latency.
            pix=doc[0].get_pixmap(matrix=fitz.Matrix(1.4,1.4),alpha=False)
            data=pix.tobytes('png'); mime='image/png'
        else:
            from PIL import Image, ImageOps
            im=Image.open(io.BytesIO(data)); im=ImageOps.exif_transpose(im).convert('RGB')
            im.thumbnail((1600,1600)); out=io.BytesIO();im.save(out,format='JPEG',quality=82)
            data=out.getvalue();mime='image/jpeg'
        prompt=("You are reviewing a residential architectural floor plan. Identify ONLY room names clearly visible, "
          "and approximate cardinal placement ONLY when north orientation is clearly established. "
          "Do not fabricate measurements, doors, walls or coordinates. "
          f"North arrow on the image points toward: {dict(N='top',E='right',S='bottom',W='left',unknown='unknown')[north]}. 'unknown' means orientation is unverified. "
          "Return strictly JSON object with keys rooms (array of objects name, zone, confidence), "
          "observations (array of short strings), uncertainties (array of short strings). "
          "Use room names only from: "+', '.join(ROOMS)+". Zone must be one of N NE E SE S SW W NW C or unknown. "
          "Confidence must be low, medium or high. If orientation is unknown use zone unknown. "
          "No more than 25 rooms. No architectural safety claims.")
        payload={'contents':[{'parts':[{'text':prompt},{'inline_data':{'mime_type':mime,'data':base64.b64encode(data).decode('ascii')}}]}],
                 'generationConfig':{'responseMimeType':'application/json','temperature':0.1}}
        model=os.environ.get('GEMINI_MODEL','gemini-2.5-flash-lite').strip()
        if model.startswith('models/'):
            model=model[len('models/'):]
        if not re.fullmatch(r'[a-zA-Z0-9._-]+', model):
            return None, 'Invalid GEMINI_MODEL setting in .env.'
        url='https://generativelanguage.googleapis.com/v1beta/models/'+model+':generateContent'

        def call_gemini(body):
            req=urllib.request.Request(
                url, data=json.dumps(body).encode('utf-8'),
                headers={'Content-Type':'application/json','x-goog-api-key':key},
                method='POST')
            with urllib.request.urlopen(req,timeout=120) as response:
                return json.load(response)

        try:
            result=call_gemini(payload)
        except urllib.error.HTTPError as first_error:
            # Some models reject responseMimeType; retry once without it only
            # when the API explicitly identifies that setting as the problem.
            raw=first_error.read(4096).decode('utf-8','replace')
            if first_error.code == 400 and ('responseMimeType' in raw or 'response_mime_type' in raw):
                payload['generationConfig'].pop('responseMimeType',None)
                result=call_gemini(payload)
            else:
                return None, gemini_http_error(first_error.code, raw, key)

        candidates=result.get('candidates') or []
        if not candidates:
            return None, 'Gemini returned no candidates. Check the model response and safety settings.'
        parts=candidates[0].get('content',{}).get('parts',[])
        content=''.join(p.get('text','') for p in parts if isinstance(p,dict))
        if not content.strip():
            return None, 'Gemini returned no text; the image may not have been processed.'
        content=re.sub(r'^```(?:json)?\s*|\s*```$', '', content.strip(), flags=re.I)
        parsed=json.loads(content)
        if not isinstance(parsed,dict):
            return None, 'Gemini returned an unexpected response structure.'
        rooms=[]
        for r in parsed.get('rooms',[])[:25]:
            if not isinstance(r,dict):continue
            name=r.get('name');zone_value=r.get('zone','unknown')
            if name not in ROOMS:continue
            if zone_value not in ('N','NE','E','SE','S','SW','W','NW','C'):zone_value='unknown'
            rooms.append({'name':name,'zone':zone_value,'confidence':str(r.get('confidence','low'))[:12]})
        return {'rooms':rooms,'observations':[str(x)[:300] for x in parsed.get('observations',[])[:12]],'uncertainties':[str(x)[:300] for x in parsed.get('uncertainties',[])[:12]],'model':model},None
    except urllib.error.HTTPError as e:
        return None, gemini_http_error(e.code, e.read(4096).decode('utf-8','replace'), key)
    except (TimeoutError, socket.timeout) as e:
        return None, 'Gemini request timed out after 120 seconds. Check connection, model availability and API latency; try a smaller image.'
    except Exception as e:
        return None,'AI review unavailable: '+str(e)[:160]

@app.post('/api/upload')
def upload():
    file=request.files.get('file')
    if not file or not file.filename:return jsonify(error='Choose a file.'),400
    ext=os.path.splitext(secure_filename(file.filename))[1].lower()
    if ext not in ('.pdf','.png','.jpg','.jpeg','.webp','.tif','.tiff'):
        return jsonify(error='Supported formats: PDF, PNG, JPG, JPEG, WEBP, TIFF.'),400
    data=file.read()
    if not data:return jsonify(error='Empty file.'),400
    extracted=''; warnings=[]; pages=1
    try:
        if ext=='.pdf':
            import fitz
            doc=fitz.open(stream=data,filetype='pdf'); pages=len(doc)
            if pages>30:return jsonify(error='PDF limit is 30 pages.'),400
            extracted='\n'.join(page.get_text() for page in doc)
        else:
            from PIL import Image
            im=Image.open(io.BytesIO(data));im.verify()
            try:
                import pytesseract
                extracted=pytesseract.image_to_string(Image.open(io.BytesIO(data)))
            except Exception:warnings.append('Local OCR unavailable; Gemini may still inspect the image.')
    except Exception as e:return jsonify(error=f'Could not process file: {str(e)[:150]}'),400
    north=request.form.get('north','unknown')
    if north not in ('N','E','S','W','unknown'):north='unknown'
    ai,ai_error=gemini_analyze(data,ext,north)
    if ai_error:warnings.append(ai_error)
    if pages>1:warnings.append('AI inspected only the first page; other PDF pages were not analyzed.')
    if north=='unknown':warnings.append('North direction is unverified. AI must not assign room directions.')
    # Only give a tentative score for user-confirmed orientation + AI detected room zones.
    evaluations=[]
    if ai and north!='unknown':
        for r in ai['rooms']:
            if r['zone']!='unknown':evaluations.append(score_room(r['name'],r['zone']))
    tentative_score=round(sum(x['score'] for x in evaluations)/len(evaluations)) if evaluations else None
    return jsonify(filename=secure_filename(file.filename),pages=pages,characters=len(extracted),text_preview=extracted[:1200],
      warnings=warnings,ai=ai,ai_score=tentative_score,ai_evaluations=evaluations,
      needs_manual_review=True,disclaimer='AI estimates are unverified. Correct detected rooms and orientation before relying on any traditional Vastu score.')

@app.post('/api/pdf')
def pdf():
    body=request.get_json(force=True)
    try:
        width,length,floors,facing,rooms=valid_plan(body)
        plans=[make_floor(width,length,rooms,i,facing) for i in range(floors+1)]
    except (ValueError,TypeError,OverflowError) as e:return jsonify(error=str(e)),400
    out=io.BytesIO(); c=canvas.Canvas(out,pagesize=A4); pw,ph=A4
    for plan in plans:
        c.setFont('Helvetica-Bold',18);c.drawString(38,ph-46,f"VASTU AI | {'Ground' if plan['floor']==0 else 'Floor '+str(plan['floor'])}")
        c.setFont('Helvetica',10);c.drawString(38,ph-64,f"Plot {width:g} x {length:g} ft | Facing {facing} | Advisory score {plan['score']}/100")
        scale=min((pw-100)/width,(ph-210)/length)
        ox=(pw-width*scale)/2; oy=115
        def rect(x,y,w,h):c.rect(ox+x*scale,oy+(length-y-h)*scale,w*scale,h*scale)
        c.setStrokeColorRGB(.12,.35,.29);c.setLineWidth(2);rect(0,0,width,length)
        hall=plan['corridor'];c.setFillColorRGB(.93,.95,.95);c.rect(ox+hall['x']*scale,oy,hall['w']*scale,length*scale,fill=1,stroke=0)
        for room in plan['rooms']:
            x,y,w,h=room['x'],room['y'],room['w'],room['h']
            c.setStrokeColorRGB(.25,.45,.39);c.setLineWidth(.8);rect(x,y,w,h)
            # break corridor-side wall with white line to show opening
            edge=x+w if room['side']=='left' else x
            dy=y+h*.5;opening=min(3,h*.35)
            c.setStrokeColorRGB(1,1,1);c.setLineWidth(3)
            c.line(ox+edge*scale,oy+(length-dy-opening/2)*scale,ox+edge*scale,oy+(length-dy+opening/2)*scale)
            c.setFillColorRGB(.1,.22,.2);c.setFont('Helvetica',max(6,min(9,w*scale/12)))
            c.drawCentredString(ox+(x+w/2)*scale,oy+(length-y-h/2)*scale,room['name'][:19])
        c.setFillColorRGB(.12,.35,.29);c.setFont('Helvetica-Bold',9);c.drawString(38,75,'Conceptual only. Doors indicative; not to scale for construction details.')
        c.setFont('Helvetica',8);c.drawString(38,61,'Vastu is traditional guidance, not scientifically established. Verify with architect/engineer.')
        c.showPage()
    c.save();out.seek(0)
    return send_file(out,mimetype='application/pdf',as_attachment=True,download_name='VASTU_AI_Floor_Plans.pdf')

@app.errorhandler(413)
def too_large(e):return jsonify(error='File too large. Maximum 15 MB.'),413

@app.get('/')
def index():return render_template('index.html')

if __name__=='__main__':
    port=int(os.environ.get('PORT','8000'))
    print(f'VASTU AI running at http://127.0.0.1:{port}',flush=True)
    app.run(host='0.0.0.0',port=port,debug=False)
