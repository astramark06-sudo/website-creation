'use strict';
const $ = id => document.getElementById(id);
let project, token, busy = false;
const status = text => { $('status').textContent = text; };
const defaultDesign = () => ({layout:'grid',typeface:'system',density:'comfortable',surface:'rounded'});
const approvals = () => ({content_rights_confirmed:false, originality_reviewed:false, publish_approved:false});
const blank = slug => ({slug,title:slug==='home'?'Home':'New page',intro:'Write an original introduction.',sections:[{heading:'Section',body:'Add original content.'}],interaction:'none'});
const fresh = () => ({version:1,title:'My website',description:'Describe your website.',theme:'teal',pages:[blank('home')],review:approvals()});
function dirty(){project.review=approvals();status('Draft changed. Refresh preview or export.');}
function action(parent,label,fn){
  const b=document.createElement('button');b.type='button';b.textContent=label;b.addEventListener('click',fn);parent.append(b);
}
function field(parent,label,value,update,opts={}){
  const wrap=document.createElement('label');wrap.textContent=label;
  const c=document.createElement(opts.choices?'select':opts.multiline?'textarea':'input');
  for(const choice of opts.choices||[]){const o=document.createElement('option');o.value=choice;o.textContent=choice;c.append(o);}
  c.value=value;c.disabled=!!opts.disabled;if(opts.max)c.maxLength=opts.max;
  c.addEventListener('input',()=>{update(c.value);dirty();});wrap.append(c);parent.append(wrap);
}
function updatePages(){
  const prior=$('preview-page').value;$('preview-page').replaceChildren();
  for(const p of project.pages){const o=document.createElement('option');o.value=p.slug;o.textContent=p.title||p.slug;$('preview-page').append(o);}
  if(project.pages.some(p=>p.slug===prior))$('preview-page').value=prior;
}
function render(){
  for(const k of ['title','description','theme'])$(k).value=project[k];
  for(const k of Object.keys(defaultDesign()))$(k).value=(project.design||defaultDesign())[k];
  $('pages').replaceChildren();
  project.pages.forEach((p,i)=>{
    const card=document.createElement('article');card.className='page-card';
    const h=document.createElement('h3');h.textContent='Page '+(i+1);card.append(h);
    field(card,'Page address',p.slug,v=>{p.slug=v;updatePages();},{disabled:i===0,max:48});
    field(card,'Page title',p.title,v=>{p.title=v;updatePages();},{max:120});
    field(card,'Introduction',p.intro,v=>p.intro=v,{multiline:true,max:1000});
    field(card,'Interaction',p.interaction,v=>p.interaction=v,{choices:['none','tasks']});
    p.sections.forEach((s,j)=>{
      const block=document.createElement('div');block.className='section-card';
      field(block,'Section heading',s.heading,v=>s.heading=v,{max:120});
      field(block,'Section body',s.body,v=>s.body=v,{multiline:true,max:4000});
      if(j>0)action(block,'Move section up',()=>{[p.sections[j-1],p.sections[j]]=[p.sections[j],p.sections[j-1]];dirty();render();});
      if(j<p.sections.length-1)action(block,'Move section down',()=>{[p.sections[j+1],p.sections[j]]=[p.sections[j],p.sections[j+1]];dirty();render();});
      if(p.sections.length>1)action(block,'Remove section',()=>{p.sections.splice(j,1);dirty();render();});
      card.append(block);
    });
    action(card,'Add section',()=>{if(p.sections.length>=12){status('Maximum 12 sections per page.');return;}p.sections.push({heading:'New section',body:'Add original content.'});dirty();render();});
    if(i>0)action(card,'Remove page',()=>{project.pages.splice(i,1);dirty();render();});
    $('pages').append(card);
  });
  updatePages();
}
function download(blob,name){
  const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
async function request(endpoint,payload){
  const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json','X-Creator-Token':token},body:JSON.stringify(payload)});
  if(!response.ok)throw new Error((await response.json()).error);
  return response;
}
async function run(fn){
  if(busy)return;busy=true;$('preview').disabled=true;$('export').disabled=true;
  try{await fn();}catch(e){status(e.message||'Request failed.');}finally{busy=false;$('preview').disabled=false;$('export').disabled=false;}
}
async function start(){
  try{
    const response=await fetch('/api/session');
    if(!response.ok)throw new Error('Session unavailable.');
    const session=await response.json();token=session.token;project=session.project;render();
    $('ai-panel').hidden=!session.ai_enabled;
    $('ai-draft').addEventListener('click',()=>run(async()=>{
      const prompt=$('ai-prompt').value.trim();if(!prompt)throw new Error('Describe your website first.');
      if(!confirm('Send these requirements to your configured offline model?'))return;
      status('Generating local draft…');
      const response=await request('/api/ai-draft',{prompt,confirmed:true});const result=await response.json();
      if(confirm('Replace the current project with this unapproved AI draft?')){project=result.project;dirty();render();$('frame').srcdoc='';status('AI draft created. Review content, design and functionality before publishing.');}
      else status('Existing project unchanged.');
    }));
    for(const k of ['title','description','theme'])$(k).addEventListener('input',()=>{project[k]=$(k).value;dirty();});
    for(const k of Object.keys(defaultDesign()))$(k).addEventListener('input',()=>{project.design={...(project.design||defaultDesign()),[k]:$(k).value};dirty();});
    $('new').addEventListener('click',()=>{if(confirm('Replace the current draft?')){project=fresh();dirty();render();$('frame').srcdoc='';}});
    $('add-page').addEventListener('click',()=>{if(project.pages.length>=20){status('Maximum 20 pages.');return;}let n=2;while(project.pages.some(p=>p.slug==='page-'+n))n++;project.pages.push(blank('page-'+n));dirty();render();});
    $('import').addEventListener('change',async()=>{try{
      const file=$('import').files[0];if(!file)return;if(file.size>131072)throw new Error('Project exceeds 128 KiB.');
      const candidate=JSON.parse(await file.text());await request('/api/preview',{spec:candidate,slug:'home'});
      if(!confirm('Replace the current draft with this imported project?'))return;
      project=candidate;dirty();render();$('frame').srcdoc='';status('Imported as an unapproved draft.');
    }catch(e){status(e.message);}finally{$('import').value='';}});
    $('analyze-reference').addEventListener('click',()=>run(async()=>{
      const file=$('reference').files[0];
      if(!file || !$('reference-authorized').checked)throw new Error('Select an authorized local HTML file and confirm permission.');
      if(file.size>65536)throw new Error('Reference exceeds 64 KiB.');
      const response=await request('/api/reference',{source:await file.text(),title:project.title,objective:project.description,authorized:true});
      const result=await response.json();
      $('reference-report').textContent=JSON.stringify({observations:result.observations,suggestions:result.suggestions,limitations:result.limitations},null,2);
      if(confirm('Replace your current project with the independently authored starter draft?')){
        project=result.project;dirty();render();$('frame').srcdoc='';status('Original reference-informed draft created. Review and customize its content.');
      }else{status('Structural report created. Existing draft unchanged.');}
      $('reference').value='';$('reference-authorized').checked=false;
    }));
    $('save').addEventListener('click',()=>{project.review=approvals();download(new Blob([JSON.stringify(project,null,2)],{type:'application/json'}),'project.json');status('Draft JSON saved.');});
    $('viewport').addEventListener('change',()=>$('frame').style.width=$('viewport').value);
    $('preview').addEventListener('click',()=>run(async()=>{status('Generating preview…');const r=await request('/api/preview',{spec:project,slug:$('preview-page').value});$('frame').srcdoc=(await r.json()).html;status('Preview generated. Test interactions after export.');}));
    $('export').addEventListener('click',()=>run(async()=>{status('Building draft…');const r=await request('/api/export',{spec:project});download(await r.blob(),'creator-project.zip');status('Verified draft exported. Nothing published.');}));
    status('Ready.');$('preview').click();
  }catch(e){status('Unable to load studio: '+e.message);}
}
start();
