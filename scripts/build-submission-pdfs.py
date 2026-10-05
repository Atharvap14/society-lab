"""Create the two review PDFs from the checked-in, evidence-grounded write-ups."""
from pathlib import Path
import html
import re
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output' / 'pdf'


def styled_text(value):
    value = value.replace('\u2011', '-').replace('\u2013', '-').replace('\u2014', ' - ')
    value = value.replace('\u2212', '-').replace('\u2192', ' to ')
    value = html.escape(value)
    value = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1', value)
    value = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', value)
    value = re.sub(r'`([^`]+)`', r'<font face="LabMono">\1</font>', value)
    return value


def page_chrome(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(colors.HexColor('#4b596c'))
    canvas.setFont('Lab', 8)
    canvas.drawString(42, 24, 'SOCIETY LAB  |  Review package  |  5 October 2026')
    canvas.drawRightString(553, 24, str(doc.page))
    canvas.restoreState()


def markdown_story(path, styles):
    lines = path.read_text(encoding='utf-8').splitlines()
    story = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line.startswith('|'):
            rows = []
            while index < len(lines) and lines[index].strip().startswith('|'):
                cells = [cell.strip() for cell in lines[index].strip().strip('|').split('|')]
                if not all(re.fullmatch(r'[:\- ]+', cell) for cell in cells):
                    rows.append(cells)
                index += 1
            if rows:
                n = len(rows[0])
                widths = ([160, 60, 291] if n == 3 and 'fingerprint' in ' '.join(rows[0]) else [511/n]*n)
                formatted = [[Paragraph(styled_text(c), styles['TableCell']) for c in row] for row in rows]
                table = Table(formatted, colWidths=widths, repeatRows=1, hAlign='LEFT')
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#eaf2f8')),
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('LINEBELOW', (0,0), (-1,0), .6, colors.HexColor('#7e99b4')),
                    ('LINEBELOW', (0,1), (-1,-1), .25, colors.HexColor('#d9e1e8')),
                    ('LEFTPADDING', (0,0), (-1,-1), 7),
                    ('RIGHTPADDING', (0,0), (-1,-1), 7),
                    ('TOPPADDING', (0,0), (-1,-1), 6),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ]))
                story.extend([table, Spacer(1, 10)])
            continue
        if line.startswith('# '):
            story.append(Paragraph(styled_text(line[2:]), styles['Title']))
        elif line.startswith('## '):
            story.append(Paragraph(styled_text(line[3:]), styles['Section']))
        else:
            paragraph = [line]
            index += 1
            while index < len(lines) and lines[index].strip() and not lines[index].startswith(('#','|')):
                paragraph.append(lines[index].strip())
                index += 1
            story.append(Paragraph(styled_text(' '.join(paragraph)), styles['Body']))
            continue
        index += 1
    return story


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, filename in [('Lab','arial.ttf'), ('LabBold','arialbd.ttf'), ('LabMono','consola.ttf')]:
        pdfmetrics.registerFont(TTFont(name, str(Path('C:/Windows/Fonts') / filename)))
    pdfmetrics.registerFontFamily('Lab', normal='Lab', bold='LabBold')
    styles = {
        'Title': ParagraphStyle('LabTitle', fontName='LabBold', fontSize=23, leading=27, textColor=colors.HexColor('#102e46'), spaceAfter=14),
        'Section': ParagraphStyle('LabSection', fontName='LabBold', fontSize=12, leading=16, spaceBefore=12, spaceAfter=7, keepWithNext=True),
        'Body': ParagraphStyle('LabBody', fontName='Lab', fontSize=10, leading=13.8, spaceAfter=8, allowOrphans=0, allowWidows=0, textColor=colors.HexColor('#23384b')),
        'TableCell': ParagraphStyle('LabTable', fontName='Lab', fontSize=8, leading=11, splitLongWords=True),
        'Caption': ParagraphStyle('LabCaption', fontName='Lab', fontSize=8.5, leading=12, spaceBefore=7, textColor=colors.HexColor('#4b596c')),
    }
    for source, filename in [('submission-writeup.md','society-lab-project.pdf'), ('real-results.md','society-lab-real-results.pdf')]:
        story = markdown_story(ROOT/'docs'/source, styles)
        screenshot = ROOT/'output'/'demo'/'village-access-recording'/'07-results.png'
        if source == 'submission-writeup.md' and False:
            visual = Image(str(screenshot))
            ratio = visual.imageHeight / visual.imageWidth
            visual.drawWidth = 511
            visual.drawHeight = min(330, 511*ratio)
            if visual.drawHeight < 511*ratio:
                visual.drawWidth = visual.drawHeight / ratio
            story.append(KeepTogether([Spacer(1,12), visual, Paragraph('Actual local Society Lab interface showing the completed, source-grounded AI Village access feasibility pilot. This screenshot is a saved result view; it does not depict a fresh execution.', styles['Caption'])]))
        if source == 'real-results.md':
            native = ROOT/'output'/'figures'/'c0a78378267faff180b1ad6306c0752d9df3595357b267de9c880b03ad51cc38'/'analysis.png'
            if native.is_file():
                story.extend([PageBreak(), Paragraph('Executed single-document reference recovery', styles['Section'])])
                figure = Image(str(native)); width, height = figure.imageWidth, figure.imageHeight
                figure.drawWidth = 511; figure.drawHeight = 511*height/width
                story.extend([figure, Paragraph('Four fresh two-role teams, two matched pairs, 64 real subject decisions. Both notes solved 2/2 verified repaired references. The saved paired 95% interval spans -100 to +100 percentage points. Secondary counts and ordinal action histories are descriptive; they do not identify a behavioral mechanism, historical cause or demonstrated note benefit.', styles['Caption'])])
            plots = ROOT/'output'/'figures'/'ai-village-september'/'readable-edition'
            if all((plots/name).is_file() for name in ('posts-by-time.png', 'name-cooccurrence.png')):
                story.extend([PageBreak(), Paragraph('Inside the real AI Village logs', styles['Section'])])
                for name, caption in [('posts-by-time.png', '1,983 recorded agent posts across six agents, September 8-11. Empty time bins describe retained chat, not agent inactivity.'), ('name-cooccurrence.png', 'Lines count posts naming both agents. GPT-5 and o3 appear together in 113 posts. This lexical graph does not establish message delivery, reading or influence.')]:
                    figure = Image(str(plots/name)); width,height=figure.imageWidth,figure.imageHeight
                    figure.drawWidth = 511; figure.drawHeight = 511*height/width
                    story.extend([figure, Paragraph(caption, styles['Caption']), Spacer(1,10)])
        target = OUT/filename
        doc = SimpleDocTemplate(str(target), pagesize=(595.28,841.89), rightMargin=42, leftMargin=42, topMargin=43, bottomMargin=42, title='Society Lab - '+source.replace('.md',''), author='Society Lab')
        doc.build(story, onFirstPage=page_chrome, onLaterPages=page_chrome)
        print(target)


if __name__ == '__main__':
    main()
