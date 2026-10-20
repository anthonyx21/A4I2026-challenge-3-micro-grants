from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
import math
out=Path(__file__).resolve().parent
im=Image.new('RGB',(2000,1800),'#070b12');d=ImageDraw.Draw(im)
base='/System/Library/Fonts/Supplemental/'
def f(n,b=False):return ImageFont.truetype(base+('Arial Bold.ttf' if b else 'Arial.ttf'),n)
def text(x,y,s,size=26,color='#b7c6d9',bold=False):d.text((x,y),s,font=f(size,bold),fill=color)
def box(x,y,w,h,title,sub,color):
 d.rounded_rectangle((x,y,x+w,y+h),20,fill='#101a28',outline=color,width=3)
 text(x+22,y+20,title,29,color,True)
 for i,s in enumerate(sub):text(x+22,y+66+i*34,s,23)
def arrow(points,color='#62778f'):
 d.line(points,fill=color,width=4);x,y=points[-1];a=math.atan2(y-points[-2][1],x-points[-2][0]);d.polygon([(x,y),(x-17*math.cos(a-.5),y-17*math.sin(a-.5)),(x-17*math.cos(a+.5),y-17*math.sin(a+.5))],fill=color)
text(80,55,'ReliefIQ',24,'#51d9e8',True)
text(80,100,'Multi-agent technical blueprint',52,'#f0f5ff',True)
text(80,173,'Challenge 03  |  Community economic resilience + micro-grants',27)
box(80,270,470,140,'Officer dashboard',['Applications, budget and questions'],'#51d9e8')
box(770,270,470,140,'Authenticated backend',['Google Cloud Run / ADK API'],'#51d9e8')
arrow([(550,340),(770,340)])
box(770,480,470,140,'Corridor Coordinator',['Routes questions • combines evidence'],'#a995ff');arrow([(1005,410),(1005,480)])
text(790,655,'ADK AgentTools • structured evidence receipts',25,'#a995ff')
xs=[80,560,1040,1520]; titles=['Grant Advisor','Cascade Analyst','Neighborhood Context','Evidence Reviewer'];subs=[['Compare feasible grants','Prepare memo findings'],['Multi-hop graph paths','Weak-link sensitivity'],['Workers and demographics','Registry and WARN context'],['Check amounts and evidence','Flag unsupported claims']];colors=['#ffd37a','#51d9e8','#6ce0af','#ffa2b7']
for x,title,sub,c in zip(xs,titles,subs,colors):
 box(x,740,400,165,title,sub,c)
 arrow([(1005,620),(1005,705),(x+200,705),(x+200,740)],'#776799')
# Two explicit MCP branches: data access and document production.
box(80,1040,830,140,'Google MCP Toolbox',['Python analysis tools → read-only BigQuery queries'],'#51d9e8')
for x in xs:
 arrow([(x+200,905),(x+200,965),(495,965),(495,1040)])
box(80,1260,830,145,'BigQuery tables + property graph',['Businesses • modeled dependencies • public context'],'#6ce0af')
arrow([(495,1180),(495,1260)],'#6ce0af')
box(1090,1040,830,140,'MCP Memo / Report Service',['Reviewed findings • named paths • assumptions'],'#ffd37a')
arrow([(280,905),(280,995),(1505,995),(1505,1040)],'#ffd37a')
text(1090,940,'Grant Advisor → MCP document tool',24,'#ffd37a',True)
box(1090,1260,830,145,'Grant Memo / Report',['Recommendation • amounts • runner-up • evidence','Downloadable Word / PDF + traversal visualization'],'#ffd37a')
arrow([(1505,1180),(1505,1260)],'#ffd37a')
box(580,1500,840,135,'Officer review + dashboard download',['Review assumptions and evidence before a decision'],'#a995ff')
arrow([(1505,1405),(1505,1450),(1000,1450),(1000,1500)],'#ffd37a')
text(80,1690,'MCP reporting service shown as a proposed component; existing agents supply the analysis and memo findings.',24,'#b7c6d9')
im.save(out/'multi-agent-blueprint-dark.png',dpi=(200,200))
im.save(out/'reliefiq-architecture-dark.png',dpi=(200,200))
im.save(out/'multi-agent-blueprint-mcp-report-dark.png',dpi=(200,200))
print(out/'multi-agent-blueprint-mcp-report-dark.png')
