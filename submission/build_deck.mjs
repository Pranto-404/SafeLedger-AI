import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {Presentation,PresentationFile} from '@oai/artifact-tool';
const root=path.resolve(process.env.SAFELEDGER_REPO_ROOT || process.cwd());
const workspaceDir=path.resolve(process.env.SAFELEDGER_DECK_WORKSPACE || path.join(root,'..'));
const output=path.join(workspaceDir,'deliverables/SafeLedger_AI_Competition_Deck_v3.pptx');
const content=JSON.parse(await fs.readFile(path.join(root,'submission/deck_content.json'),'utf8'));
const p=Presentation.create({slideSize:{width:1280,height:720}});
const font='DejaVu Sans',ink='#193336',green='#086655';
function text(slide,value,left,top,width,height,size=28,bold=false,color=ink){const shape=slide.shapes.add({name:'text-'+slide.shapes.items.length,geometry:'textbox',position:{left,top,width,height},fill:'none',line:{style:'solid',fill:'none',width:0}});shape.text=value;shape.text.style={typeface:font,fontSize:size,bold,color,autoFit:'none',insets:0};return shape;}
for(const [i,item] of content.entries()){
 const s=p.slides.add();s.background.fill=i===0?'#163e36':'#ffffff';
 if(i===0){text(s,item.title,80,165,1120,100,76,true,'#ffffff');text(s,item.subtitle,80,285,1100,65,43,false,'#cce7da');text(s,item.body,80,410,1030,105,31,false,'#ffffff');text(s,'Topic E   2026 Shenzhen International FinTech Competition',80,610,1100,34,20,false,'#cce7da');}
 else{
  text(s,item.title,70,55,1140,85,44,true);
  if(item.image){s.images.add({blob:new Uint8Array(await fs.readFile(path.join(root,item.image))),contentType:'image/png',alt:'Actual synthetic SafeLedger financial dashboard',fit:'contain',position:{left:510,top:160,width:700,height:500}});text(s,item.body,70,200,410,140,40,true,green);for(const[j,line]of item.lines.entries())text(s,line,70,365+j*58,410,52,24);}
  else if(item.table){const rows=item.table.length,cols=item.table[0].length;const t=s.tables.add({rows,columns:cols,left:70,top:168,width:1140,height:rows===6?360:330,columnTracks:item.table[0].map(()=>({mode:'fr',value:1})),values:item.table});for(let r=0;r<rows;r++)for(let c=0;c<cols;c++){const cell=t.getCell(r,c);cell.fill=r===0?green:r%2?'#f1f6f2':'#ffffff';cell.text.style={typeface:font,fontSize:cols===3?24:25,color:r===0?'#ffffff':ink,bold:r===0,verticalAlignment:'middle',insets:12,autoFit:'none'};}text(s,item.body,70,575,1120,90,27,false,green);}
  else if(item.steps){for(const[j,line]of item.steps.entries())text(s,line,j<4?80:700,185+(j<4?j:j-4)*87,j<4?570:500,70,30,j===3||j===4);text(s,item.body,80,595,1120,60,25,false,green);}
  else{const start=item.lines.length===3?280:190;if(i===1)text(s,item.body,75,160,1100,100,35,true,green);for(const[j,line]of item.lines.entries())text(s,line,80,start+j*(i===1?100:95),1100,82,30);if(i!==1)text(s,item.body,80,600,1100,70,26,true,green);}
  text(s,String(i+1).padStart(2,'0'),1180,675,40,25,16,false,'#52695f');
 }
 s.speakerNotes.text=`Target ${item.timing_seconds} seconds. ${item.notes}`;
}
await fs.mkdir(path.join(workspaceDir,'deck-build/rendered'),{recursive:true});
const candidate=path.join(workspaceDir,'deck-build/candidate.pptx');await(await PresentationFile.exportPptx(p)).save(candidate);
const skill=process.env.SAFELEDGER_PRESENTATIONS_SKILL || '/root/.codex/skills/builtins/presentations';const{finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
await finalizePresentation({workspaceDir,candidatePath:candidate,finalPath:output,pythonExecutable:process.env.CODEX_PRIMARY_RUNTIME_PYTHON,integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit',...[5,6,7,9].flatMap(n=>['--require-native-table-slide',String(n)])],explicitTotalSlideCount:10,requiredNativeTableOwnerSlides:[5,6,7,9],fontPolicy:{basis:'design',families:[font]},verifyArtifactToolImport:true,receiptPath:path.join(workspaceDir,'deck-build/validation-v3.json')});
for(const[i,s]of p.slides.items.entries()){const image=await p.export({slide:s,format:'png',scale:1});await fs.writeFile(path.join(workspaceDir,`deck-build/rendered/slide-${i+1}.png`),new Uint8Array(await image.arrayBuffer()));}
console.log(JSON.stringify({slides:content.length,target_seconds:content.reduce((n,s)=>n+s.timing_seconds,0),output}));
