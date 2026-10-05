"""Original geometric explainer; no UI reconstruction, providers or hosting."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

W,H,FPS,DURATION=1920,1080,24,25
BG=(13,21,33); WHITE=(234,241,248); TEAL=(80,218,191); GOLD=(255,188,103); MUTED=(128,149,168)

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def font(size,bold=False):
    return ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf' if bold else 'C:/Windows/Fonts/segoeui.ttf',size)

def ease(v):
    v=max(0,min(1,v));return v*v*(3-2*v)

def mix(a,b,v):return tuple(round(x+(y-x)*v) for x,y in zip(a,b))

def centered(d,xy,text,size=34,fill=WHITE,bold=False):
    f=font(size,bold);box=d.textbbox((0,0),text,font=f)
    d.text((xy[0]-(box[2]-box[0])/2,xy[1]-(box[3]-box[1])/2),text,font=f,fill=fill)

def line(d,a,b,color=TEAL,width=3):d.line((*a,*b),fill=color,width=width)

def pulse(d,a,b,t,color=TEAL):
    v=(t*.38)%1;p=(a[0]+(b[0]-a[0])*v,a[1]+(b[1]-a[1])*v)
    for r in (15,8):d.ellipse((p[0]-r,p[1]-r,p[0]+r,p[1]+r),fill=mix(BG,color,.2 if r==15 else 1))

def document(d,x,y,alpha=1,label='Shared document'):
    c=mix(BG,WHITE,alpha);d.rounded_rectangle((x-74,y-97,x+74,y+97),radius=10,outline=c,width=4)
    for k in range(4):line(d,(x-43,y-43+k*27),(x+43,y-43+k*27),mix(BG,MUTED,alpha),3)
    centered(d,(x,y+131),label,29,c)

def frame(t):
    im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
    for x in range(80,W,80):
        for y in range(120,890,80):d.ellipse((x,y,x+2,y+2),fill=(31,44,60))
    d.text((64,42),'SOCIETY LAB',font=font(29,True),fill=TEAL)
    d.text((1210,48),'Original illustration · product recording follows',font=font(23),fill=MUTED)
    phase=ease((t-4)/2);cx=760-270*phase;cy=430
    pts=[(cx+210*math.cos(-math.pi/2+k*math.pi/3),cy+210*math.sin(-math.pi/2+k*math.pi/3)) for k in range(6)]
    for k in range(6):
        a,b=pts[k],pts[(k+1)%6];line(d,a,b,(43,73,83),3)
        if 2<t<11:pulse(d,a,b,t+k*.63)
    for k,(x,y) in enumerate(pts):
        r=39+3*math.sin(t*1.5+k);c=TEAL if k%2==0 else GOLD
        d.ellipse((x-r,y-r,x+r,y+r),fill=mix(BG,c,.15),outline=c,width=3)
        centered(d,(x,y-2),chr(65+k),32,c,True)
    centered(d,(cx,cy+283),'Agents',32,MUTED)
    doc_alpha=ease((t-4.7)/1.2);dx=1290;dy=420
    if doc_alpha:
        document(d,dx,dy,doc_alpha)
        a=pts[1];end=(dx-88,dy)
        color=mix(BG,TEAL,doc_alpha)
        line(d,a,end,color,4)
        if t<9:pulse(d,a,end,t)
        if t>=8:
            p=(980,420);break_alpha=ease((t-8)/.8)
            d.ellipse((p[0]-38,p[1]-38,p[0]+38,p[1]+38),fill=BG)
            c=mix(BG,GOLD,break_alpha)
            line(d,(p[0]-19,p[1]-19),(p[0]+19,p[1]+19),c,5);line(d,(p[0]-19,p[1]+19),(p[0]+19,p[1]-19),c,5)
            centered(d,(985,340),'Link fails',31,c,True)
    causes_alpha=ease((t-10.5)/1.5)*(1-ease((t-19)/1))
    if causes_alpha:
        for i,label in enumerate(['Wrong reference?','Permission?','Browser state?']):
            x=870+i*320;y=716-24*ease((t-11)/1.5)
            c=mix(BG,MUTED,causes_alpha)
            d.rounded_rectangle((x-130,y-43,x+130,y+43),radius=15,outline=c,width=2)
            centered(d,(x,y),label,27,c)
    controlled=ease((t-16)/2)
    if controlled:
        d.rounded_rectangle((801,233,1758,787),radius=20,outline=mix(BG,TEAL,controlled),width=3)
        centered(d,(1280,270),'Controlled world',32,mix(BG,TEAL,controlled),True)
        centered(d,(1280,809),'Known tool rules. Original hidden state stays unknown.',25,mix(BG,MUTED,controlled))
    if t>=20:
        a=ease((t-20)/1.2);x=950;y=542
        d.rounded_rectangle((817,510,1740,633),radius=12,fill=BG)
        for j,label in enumerate(['Neutral note','Check the link first']):
            bx=1030+j*485;c=mix(BG,TEAL if j else GOLD,a)
            d.rounded_rectangle((bx-185,y-34,bx+185,y+52),radius=12,outline=c,width=3)
            centered(d,(bx,y+7),label,29,c)
        centered(d,(1280,641),'Fresh teams · matched starting worlds',26,mix(BG,WHITE,a))
    if t<4:caption='Agents work together.'
    elif t<8:caption='They share links and updates.'
    elif t<11:caption='A link fails.'
    elif t<16:caption='What caused it? We do not know yet.'
    elif t<20:caption='We build a world with the right tools.'
    else:caption='Then we test one change.'
    centered(d,(960,958),caption,53,WHITE,True)
    line(d,(64,1030),(1856,1030),(33,49,67),3);line(d,(64,1030),(64+1792*min(1,t/DURATION),1030),TEAL,3)
    return im

def build_intro(output):
    output=Path(output).absolute();output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():raise ValueError('Use a fresh immutable edition')
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    args=[ffmpeg,'-hide_banner','-loglevel','warning','-nostdin','-n','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','pipe:0','-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart','-an',str(output)]
    log=output.with_suffix('.ffmpeg.stderr.bin');digest=hashlib.sha256()
    with log.open('wb') as err:
        p=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=err)
        try:
            for i in range(FPS*DURATION):
                raw=frame(i/FPS).tobytes();digest.update(raw);p.stdin.write(raw)
            p.stdin.close();code=p.wait(timeout=180)
        except BaseException:
            p.kill();p.wait();raise
    if code:raise RuntimeError('Encoding failed; byte log retained')
    count,duration=imageio_ffmpeg.count_frames_and_secs(str(output))
    reader=imageio_ffmpeg.read_frames(str(output));metadata=next(reader);reader.close()
    if count!=FPS*DURATION or abs(duration-DURATION)>.02 or list(metadata['source_size'])!=[W,H]:raise ValueError('Decoded intro did not match')
    proof={'kind':'original_geometric_motion_intro','path':str(output),'sha256':sha(output),'bytes':output.stat().st_size,'dimensions':[W,H],'fps':FPS,'frames':count,'duration_seconds':duration,'rendered_raw_frames_sha256':digest.hexdigest(),'script_sha256':sha(__file__),'ffmpeg_sha256':sha(ffmpeg),'verified':True,'model_calls':0,'database_writes':0,'scope':'Original illustrative geometry, not an AI Village record, actual UI, historical reconstruction, hidden reasoning or scientific result. Continuous independently rendered frames; no assets copied from another creator.','created_utc':datetime.now(timezone.utc).isoformat()}
    output.with_suffix('.verification.json').write_text(json.dumps(proof,indent=2),encoding='utf-8');print(json.dumps(proof,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();build_intro(args.output)
