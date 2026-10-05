"""Join an animated intro to timestamped actual product captures, preserving timing.

No generated product frames or interpolated actions. CFR holds the most recent
actual capture; its sampling gaps are disclosed. This is not a continuous native
screen recorder. Root supplies the actual capture timestamps and provenance.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess

from PIL import Image,ImageDraw,ImageFont,ImageChops
import imageio_ffmpeg

W,H,FPS=1920,1080,24

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def stamp(text):
    if type(text)is not str or len(text)>80:raise ValueError('Exact UTC timestamp required')
    dt=datetime.fromisoformat(text.replace('Z','+00:00'))
    if dt.tzinfo is None or dt.utcoffset().total_seconds()!=0:raise ValueError('UTC timestamps required')
    return dt

def local(path,root,base=None):
    p=Path(path)
    if not p.is_absolute():
        p=(Path(base)/p if base is not None else p.absolute())
    for part in (p,*p.parents):
        if part.is_symlink() or (hasattr(part,'is_junction') and part.is_junction()):raise ValueError('No linked capture paths')
    p=p.resolve(strict=True)
    if not p.is_relative_to(root) or not p.is_file():raise ValueError('Input outside allowed root')
    return p

def load(path,allowed_root):
    root=Path(allowed_root).resolve(strict=True);path=Path(path).resolve(strict=True)
    with path.open('rb')as f:raw=f.read(1024*1024+1)
    if len(raw)>1024*1024:raise ValueError('Manifest exceeds1MiB')
    m=json.loads(raw.decode('utf-8-sig'))
    if type(m)is not dict or type(m.get('frames'))is not list or not 1<=len(m['frames'])<=1200:raise ValueError('Supply1..1200actual captures')
    rows=[];prev=None
    for row in m['frames']:
        if type(row)is not dict or not{'image','captured_at_utc'}<=set(row):raise ValueError('Actual image and capture time required')
        candidate=Path(row['image'])
        base=path.parent if not candidate.is_absolute() and not candidate.exists() else None
        p=local(row['image'],root,base);time=stamp(row['captured_at_utc']);digest=sha(p)
        if p.suffix.lower()not in{'.png','.jpg','.jpeg'}or p.stat().st_size>32*1024*1024:raise ValueError('Bounded PNG/JPEG required')
        if row.get('sha256',digest)!=digest:raise ValueError('Capture hash mismatch')
        if prev is not None and time<=prev:raise ValueError('Capture times must strictly increase')
        caption=row.get('caption','')
        if type(caption)is not str or len(caption)>160 or '\n'in caption:raise ValueError('One short plain-English caption')
        rows.append({'image':str(p),'captured_at_utc':time.isoformat(),'capture_started_at_utc':row.get('capture_started_at_utc'),'sha256':digest,'caption':caption,'time':time});prev=time
    start=stamp(m.get('started_at_utc',rows[0]['captured_at_utc']));end=stamp(m.get('ended_at_utc',rows[-1]['captured_at_utc']))
    if not 0<=(rows[0]['time']-start).total_seconds()<=1800 or end<rows[-1]['time'] or (end-rows[-1]['time']).total_seconds()>2:raise ValueError('Unknown leading/trailing interval cannot be reconstructed')
    omitted_leading_seconds=(rows[0]['time']-start).total_seconds();start=rows[0]['time']
    duration=(end-start).total_seconds()
    if not 10<=duration<=1800:raise ValueError('Actual capture span must be10..1800seconds')
    declared=m.get('segments',[])
    if type(declared)is not list or len(declared)>32:raise ValueError('At most32 explicit captured segments')
    segments=[]
    if not declared:segments=[{'id':'continuous-sampled-span','rows':rows,'start':start,'end':end,'duration':duration,'label':''}]
    else:
        previous_end=None
        for i,seg in enumerate(declared):
            if type(seg)is not dict or not{'started_at_utc','ended_at_utc'}<=set(seg):raise ValueError('Explicit segment UTC endpoints required')
            a,b=stamp(seg['started_at_utc']),stamp(seg['ended_at_utc']);label=seg.get('label','Recorded segment')
            if type(label)is not str or len(label)>100 or b<=a or (previous_end is not None and a<previous_end):raise ValueError('Bounded chronological nonoverlapping segments required')
            selected=[r for r in rows if a<=r['time']<=b]
            if not selected or (selected[0]['time']-a).total_seconds()>2 or (b-selected[-1]['time']).total_seconds()>2:raise ValueError('Cut cannot reconstruct unknown boundary content')
            a=selected[0]['time'];span=(b-a).total_seconds()
            if span<.25:raise ValueError('Captured segment too short')
            segments.append({'id':seg.get('id',f'segment-{i+1}'),'rows':selected,'start':a,'end':b,'duration':span,'label':label});previous_end=b
    retained=sum(s['duration']for s in segments)
    if not 10<=retained<=300:raise ValueError('Retain10..300seconds; long waits require explicitly declared cuts')
    return{'path':str(path),'sha256':sha(path),'rows':rows,'segments':segments,'start':start,'end':end,'duration':retained,'full_capture_span_seconds':duration,'explicit_cut_count':max(0,len(segments)-1),'omitted_wait_seconds':duration-retained,'omitted_unknown_leading_seconds':omitted_leading_seconds,'declared_provenance':m.get('capture_scope',m.get('provenance','Root-supplied actual product capture times; not independently attested'))}

def stable_crop(rows):
    groups={}
    for row in rows:
        if sha(row['image'])!=row['sha256']:raise ValueError('Capture bytes changed')
        with Image.open(row['image'])as source:
            im=source.convert('RGB')
            if im.width*im.height>20_000_000:raise ValueError('Input exceeds20Mpixels')
            dimensions=im.size;bounds=groups.get(dimensions);bg=im.getpixel((im.width-1,im.height-1))
            b=ImageChops.difference(im,Image.new('RGB',im.size,bg)).getbbox()
            if b:bounds=b if bounds is None else(min(bounds[0],b[0]),min(bounds[1],b[1]),max(bounds[2],b[2]),max(bounds[3],b[3]))
            groups[dimensions]=bounds
    return{dimensions:([max(0,bounds[0]-16),max(0,bounds[1]-16),min(dimensions[0],bounds[2]+16),min(dimensions[1],bounds[3]+16)]if bounds else[0,0,*dimensions])for dimensions,bounds in groups.items()}

def compose(row,fixed_crop=None):
    if sha(row['image'])!=row['sha256']:raise ValueError('Capture changed before rendering')
    with Image.open(row['image'])as f:
        im=f.convert('RGB');size=im.size
        if im.width*im.height>20_000_000:raise ValueError('Input exceeds20Mpixels')
        # Remove uniform canvas padding only. Full differing-pixel bounding box
        # plus margin remains, so no captured action or panel is fabricated.
        bg=im.getpixel((im.width-1,im.height-1));bbox=ImageChops.difference(im,Image.new('RGB',im.size,bg)).getbbox()
        crop=[0,0,im.width,im.height]
        if fixed_crop is not None:
            crop=fixed_crop[im.size]if type(fixed_crop)is dict else fixed_crop
            if bbox and not(crop[0]<=bbox[0]and crop[1]<=bbox[1]and crop[2]>=bbox[2]and crop[3]>=bbox[3]):raise ValueError('Fixed crop removes captured content')
            im=im.crop(tuple(crop))
        elif bbox:
            crop=[max(0,bbox[0]-16),max(0,bbox[1]-16),min(im.width,bbox[2]+16),min(im.height,bbox[3]+16)];im=im.crop(crop)
        im.thumbnail((1856,880),Image.Resampling.LANCZOS)
        canvas=Image.new('RGB',(W,H),'#0d1521');canvas.paste(im,((W-im.width)//2,54+(880-im.height)//2))
    d=ImageDraw.Draw(canvas);font=lambda n:ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',n)
    d.text((32,14),'SOCIETY LAB / actual recorded product usage',font=font(26),fill='#50dabf')
    d.text((1185,18),row['captured_at_utc'],font=font(22),fill='#8fabbc')
    caption=row['caption']or'Actual capture. Original timing is preserved.'
    f=font(34);box=d.textbbox((0,0),caption,font=f)
    if box[2]>1856:raise ValueError('Shorten caption to fit one visible line')
    d.text(((W-box[2])/2,969),caption,font=f,fill='#eaf1f8')
    d.text((32,1035),'Captured screens only. No interpolated product actions.',font=font(21),fill='#8fabbc')
    return canvas.tobytes(),{'original_size':list(size),'blank_padding_crop':crop,'display_size':list(im.size)}

def build(intro,manifest,output,allowed_root):
    root=Path(allowed_root).resolve(strict=True);intro=local(intro,root);output=Path(output).absolute()
    if output.exists():raise ValueError('Preserve earlier editions; use a new name')
    packet=load(manifest,root);output.parent.mkdir(parents=True,exist_ok=True);crop=stable_crop(packet['rows'])
    intro_count,intro_duration=imageio_ffmpeg.count_frames_and_secs(str(intro))
    reader=imageio_ffmpeg.read_frames(str(intro));meta=next(reader)
    if list(meta['source_size'])!=[W,H]or abs(meta['fps']-FPS)>.01:reader.close();raise ValueError('Intro must be1080p24fps')
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe();args=[ffmpeg,'-hide_banner','-loglevel','warning','-nostdin','-n','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','pipe:0','-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart','-an',str(output)]
    product_frames=sum(round(s['duration']*FPS)for s in packet['segments']);timeline=[];digest=hashlib.sha256()
    with output.with_suffix('.ffmpeg.stderr.bin').open('wb')as err:
        process=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=err)
        try:
            for raw in reader:digest.update(raw);process.stdin.write(raw)
            frame_offset=0
            for seg in packet['segments']:
                idx=-1;raw=None
                for i in range(round(seg['duration']*FPS)):
                    time=seg['start'].timestamp()+i/FPS;j=idx
                    while j+1<len(seg['rows'])and seg['rows'][j+1]['time'].timestamp()<=time:j+=1
                    if j<0:raise ValueError('No actual capture for start')
                    if j!=idx:
                        idx=j;display_row={**seg['rows'][idx],'caption':seg['rows'][idx]['caption']or seg['label']}
                        raw,transform=compose(display_row,crop);timeline.append({**{k:v for k,v in display_row.items()if k!='time'},**transform,'segment_id':seg['id'],'cut_label':seg['label'],'product_frame':frame_offset+i,'video_seconds':intro_duration+(frame_offset+i)/FPS})
                    digest.update(raw);process.stdin.write(raw)
                frame_offset+=round(seg['duration']*FPS)
            process.stdin.close();returncode=process.wait(timeout=300)
        except BaseException:process.kill();process.wait();raise
        finally:reader.close()
    if returncode:raise RuntimeError('Encoding failed; logs retained')
    count,duration=imageio_ffmpeg.count_frames_and_secs(str(output));expected=intro_count+product_frames
    if count!=expected or abs(duration-expected/FPS)>.02:raise ValueError('Decoded duration/count changed')
    holds=[(b['time']-a['time']).total_seconds()for a,b in zip(packet['rows'],packet['rows'][1:])]
    if sha(packet['path'])!=packet['sha256']:raise ValueError('Capture manifest changed during encoding')
    proof={'kind':'motion_intro_and_timestamped_actual_usage','video':{'path':str(output),'sha256':sha(output),'bytes':output.stat().st_size,'dimensions':[W,H],'fps':FPS,'frames':count,'duration_seconds':duration},'intro':{'path':str(intro),'sha256':sha(intro),'duration_seconds':intro_duration},'capture_manifest':{k:v for k,v in packet.items()if k not in{'rows','segments','start','end'}},'retained_segments':[{'id':s['id'],'started_at_utc':s['start'].isoformat(),'ended_at_utc':s['end'].isoformat(),'duration_seconds':s['duration'],'label':s['label']}for s in packet['segments']],'actual_capture_count':len(packet['rows']),'maximum_observation_gap_seconds':max(holds,default=0),'timeline':timeline,'rendered_frames_sha256':digest.hexdigest(),'script_sha256':sha(__file__),'verified':True,'scope':'Animated original illustration followed by actual timestamped product capture sequence. The last captured screen is held at CFR until the next actual capture; gaps and explicit wait cuts remain disclosed. No interpolation or invented UI/action. This is not a continuous native screen recording. Source provenance is declared by capture operator, not independently authenticated by encoding.','model_calls':0,'database_writes':0}
    output.with_suffix('.verification.json').write_text(json.dumps(proof,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in proof.items()if k!='timeline'},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--intro',required=True);p.add_argument('--manifest',required=True);p.add_argument('--output',required=True);p.add_argument('--allowed-root',default='output');a=p.parse_args();build(a.intro,a.manifest,a.output,a.allowed_root)
