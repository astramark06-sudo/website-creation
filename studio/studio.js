'use strict';
const $ = id => document.getElementById(id);
let project, token, busy = false, latestRelease = null, latestBrowser = null, draftRevision = 0;
let invalidateRelationalCheck = () => {};
const status = text => { $('status').textContent = text; };
const defaultDesign = () => ({layout:'grid',typeface:'system',density:'comfortable',surface:'rounded'});
const approvals = () => ({content_rights_confirmed:false, originality_reviewed:false, publish_approved:false});
const blank = slug => ({slug,title:slug==='home'?'Home':'New page',intro:'Write an original introduction.',sections:[{heading:'Section',body:'Add original content.'}],interaction:'none'});
const fresh = () => ({version:1,title:'My website',description:'Describe your website.',theme:'teal',pages:[blank('home')],review:approvals()});
function dirty(){invalidateRelationalCheck();project.review=approvals();draftRevision++;latestRelease=null;latestBrowser=null;$('browser-save').disabled=true;$('browser-check-results').replaceChildren();$('browser-check-status').textContent='Draft changed. Run new browser checks.';$('release-save').disabled=true;$('release-results').replaceChildren();$('release-status').textContent='Draft changed. Run a new release check.';status('Draft changed. Refresh preview or export.');}
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
    field(card,'Interaction',p.interaction,v=>p.interaction=v,{choices:['none','tasks','search']});
    p.sections.forEach((s,j)=>{
      const block=document.createElement('div');block.className='section-card';
      field(block,'Component type',s.kind||'card',v=>{s.kind=v;render();},{choices:['card','article','callout','faq','list','steps','metrics','timeline','table']});
      field(block,'Section heading',s.heading,v=>s.heading=v,{max:120});
      field(block,'Section body',s.body,v=>s.body=v,{multiline:true,max:4000});
      const hints={
        list:'One item per line (up to 30).',steps:'One step per line (up to 30).',
        metrics:'One metric per line: Label | Value (up to 12).',
        timeline:'One event per line: Label | Details (up to 20).',
        table:'First line is the header; use 2–6 pipe-separated cells per row and up to 30 data rows.'
      };
      if(hints[s.kind]){const hint=document.createElement('p');hint.className='section-hint';hint.textContent=hints[s.kind];block.append(hint);}
      const handle=document.createElement('button');handle.type='button';handle.className='drag-handle';handle.draggable=true;handle.textContent='Drag to reorder';handle.setAttribute('aria-label','Drag section '+(j+1)+' to reorder; use move buttons for keyboard ordering');
      handle.addEventListener('dragstart',event=>{event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain',JSON.stringify({page:i,section:j}));});
      block.addEventListener('dragover',event=>{event.preventDefault();event.dataTransfer.dropEffect='move';});
      block.addEventListener('drop',event=>{event.preventDefault();try{
        const move=JSON.parse(event.dataTransfer.getData('text/plain'));
        if(!move||move.page!==i||!Number.isInteger(move.section)||move.section<0||move.section>=p.sections.length||move.section===j)return;
        const [item]=p.sections.splice(move.section,1);p.sections.splice(j,0,item);dirty();render();
      }catch(_){/* Ignore unrelated dragged data. */}});
      block.append(handle);
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
function showToolResults(heading, value){
  const host=$('tool-results');host.replaceChildren();
  const h=document.createElement('h3');h.textContent=heading;host.append(h);
  const pre=document.createElement('pre');pre.textContent=JSON.stringify(value,null,2);host.append(pre);
}
function showSources(sources){
  const host=$('tool-results');host.replaceChildren();
  for(const source of sources){
    const card=document.createElement('article');card.className='section-card';
    const h=document.createElement('h3');h.textContent=source.name;card.append(h);
    const p=document.createElement('p');p.textContent=source.import_policy+' · '+source.notes;card.append(p);
    const u=new URL(source.url);
    if(u.protocol==='https:'&&!u.username&&!u.password){
      const link=document.createElement('a');link.href=u.href;link.target='_blank';link.rel='noopener noreferrer';link.textContent='Open original resource';card.append(link);
    }
    host.append(card);
  }
}
function initToolCenter(){
  let loaded=false, loading=false;
  const toolStatus=message=>{$('tool-status').textContent=message;};
  const execute=async fn=>{
    if(loading)return;loading=true;
    $('source-search').disabled=true;$('tool-plan').disabled=true;
    try{await fn();}catch(e){toolStatus(e.message||'Tool request failed.');}
    finally{loading=false;$('source-search').disabled=false;$('tool-plan').disabled=false;}
  };
  $('tool-center').addEventListener('toggle',()=>{
    if(!$('tool-center').open||loaded)return;
    execute(async()=>{
      const result=await(await request('/api/tool-overview',{})).json();
      $('tool-counts').textContent=result.counts.registered_tools+' registered tools · '+result.counts.sources+' sources · '+result.counts.profiles+' profiles. Catalogue entries are not active connections.';
      for(const profile of result.profiles){const o=document.createElement('option');o.value=profile.id;o.textContent=profile.id+' ('+profile.framework+')';$('tool-profile').append(o);}
      for(const policy of result.import_policies){const o=document.createElement('option');o.value=policy;o.textContent=policy;$('source-policy').append(o);}
      loaded=true;toolStatus('Read-only catalogue ready.');
    });
  });
  $('tool-plan').addEventListener('click',()=>execute(async()=>{
    const result=await(await request('/api/tool-plan',{profile:$('tool-profile').value,objective:project.description})).json();
    showToolResults('Proposed stack (not installed)',result);
    toolStatus('Development plan prepared. No tools installed.');
  }));
  $('source-search').addEventListener('click',()=>execute(async()=>{
    const args={query:$('source-query').value.trim()};if($('source-policy').value)args.import_policy=$('source-policy').value;
    const result=await(await request('/api/tool-query',{tool:'search_sources',arguments:args})).json();
    showSources(result.sources);toolStatus(result.sources.length+' matching sources. Review individual terms and licenses.');
  }));
}
function renderRelease(report){
  const host=$('release-results');host.replaceChildren();
  const summary=document.createElement('p');summary.textContent=report.pages+' pages · '+report.generated_files+' generated files. Publication readiness not established.';host.append(summary);
  const list=document.createElement('ul');list.className='release-gates';
  for(const gate of report.gates){
    const li=document.createElement('li'),title=document.createElement('strong'),evidence=document.createElement('span');
    title.textContent=gate.name+' — '+gate.status;evidence.textContent=gate.evidence;li.append(title,evidence);list.append(li);
  }
  host.append(list);
  for(const warning of [...report.warnings,...report.limitations]){const p=document.createElement('p');p.className='section-hint';p.textContent=warning;host.append(p);}
}
async function start(){
  try{
    const response=await fetch('/api/session');
    if(!response.ok)throw new Error('Session unavailable.');
    const session=await response.json();token=session.token;project=session.project;render();initToolCenter();
    $('ai-panel').hidden=!session.ai_enabled;$('browser-check-panel').hidden=!session.browser_checks_enabled;
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
    $('vision-panel').hidden=!session.vision_enabled;
    $('vision-analyze').addEventListener('click',()=>run(async()=>{
      const file=$('visual-file').files[0];
      if(!session.vision_enabled||!file||!$('visual-authorized').checked||!$('vision-consent').checked)
        throw new Error('Select an authorized screenshot and confirm local model consent.');
      const revision=draftRevision;
      status('Preparing reduced screenshot for the local model…');
      try{
        const image=await window.prepareVisionReference(file);
        if(revision!==draftRevision||$('visual-file').files[0]!==file||!$('visual-authorized').checked||!$('vision-consent').checked){
          status('Screenshot, consent or draft changed. Run analysis again.');return;
        }
        const result=await(await request('/api/vision-reference',{image,title:project.title,objective:project.description,authorized:true})).json();
        if(revision!==draftRevision||$('visual-file').files[0]!==file||!$('visual-authorized').checked||!$('vision-consent').checked){
          status('Screenshot, consent or draft changed. Existing draft unchanged.');return;
        }
        $('visual-report').textContent=JSON.stringify({selection:result.selection,limitations:result.limitations},null,2);
        if(confirm('Replace the current draft with the original preset-based proposal?')){
          project=result.project;dirty();render();$('frame').srcdoc='';status('Local vision draft created. Review and replace starter content.');
        }else status('Local vision report created. Existing draft unchanged.');
      }finally{$('visual-file').value='';$('visual-authorized').checked=false;$('vision-consent').checked=false;}
    }));
    $('visual-analyze').addEventListener('click',()=>run(async()=>{
      const file=$('visual-file').files[0];
      if(!file||!$('visual-authorized').checked)throw new Error('Select an authorized screenshot and confirm permission.');
      const revision=draftRevision;
      status('Analyzing screenshot locally…');
      try{
        const observations=await window.analyzeVisualReference(file);
        if(revision!==draftRevision){status('Draft changed. Run screenshot analysis again.');return;}
        const result=await(await request('/api/visual-reference',{observations,title:project.title,objective:project.description,authorized:true})).json();
        if(revision!==draftRevision){status('Draft changed. Run screenshot analysis again.');return;}
        $('visual-report').textContent=JSON.stringify({observations:result.observations,suggestions:result.suggestions,limitations:result.limitations},null,2);
        if(confirm('Replace the current draft with this independently designed starter?')){
          project=result.project;dirty();render();$('frame').srcdoc='';status('Screenshot-informed draft created. Review original content and layout.');
        }else status('Visual report created. Existing draft unchanged.');
      }finally{$('visual-file').value='';$('visual-authorized').checked=false;}
    }));
    $('save').addEventListener('click',()=>{project.review=approvals();download(new Blob([JSON.stringify(project)],{type:'application/json'}),'project.json');status('Draft JSON saved.');});
    $('viewport').addEventListener('change',()=>$('frame').style.width=$('viewport').value);
    $('preview').addEventListener('click',()=>run(async()=>{status('Generating preview…');const r=await request('/api/preview',{spec:project,slug:$('preview-page').value});$('frame').srcdoc=(await r.json()).html;status('Preview generated. Test interactions after export.');}));
    $('export').addEventListener('click',()=>run(async()=>{status('Building draft…');const r=await request('/api/export',{spec:project});download(await r.blob(),'creator-project.zip');status('Verified draft exported. Nothing published.');}));
    $('release-check').addEventListener('click',()=>run(async()=>{
      const revision=draftRevision;
      $('release-save').disabled=true;latestRelease=null;$('release-results').replaceChildren();
      $('release-status').textContent='Checking this draft…';
      try{
        const result=await(await request('/api/release-report',{spec:project})).json();
        if(revision!==draftRevision)return;
        latestRelease=result;renderRelease(result);$('release-save').disabled=false;
        $('release-status').textContent='Report generated. Human and project-specific testing gates remain.';
      }catch(e){if(revision===draftRevision)$('release-status').textContent='Release check failed: '+e.message;throw e;}
    }));
    $('browser-check').addEventListener('click',()=>run(async()=>{
      const revision=draftRevision;
      latestBrowser=null;$('browser-save').disabled=true;$('browser-check-results').replaceChildren();
      $('browser-check-status').textContent='Running local Chromium checks…';
      try{
        const result=await(await request('/api/browser-check',{spec:project,confirmed:true})).json();
        if(revision!==draftRevision)return;
        latestBrowser=result;$('browser-save').disabled=false;
        $('browser-check-status').textContent=result.status+' — '+result.results.length+' page/viewport checks. Not a full accessibility or deployment audit.';
        const pre=document.createElement('pre');pre.style.whiteSpace='pre-wrap';pre.style.overflowWrap='anywhere';
        pre.textContent=JSON.stringify({browser:result.browser,viewports:result.viewports,findings:result.findings,limitations:result.limitations},null,2);
        $('browser-check-results').append(pre);
      }catch(e){if(revision===draftRevision)$('browser-check-status').textContent='Browser check failed. Confirm Playwright and Chromium are installed and the draft is valid.';throw e;}
    }));
    $('browser-save').addEventListener('click',()=>{if(latestBrowser)download(new Blob([JSON.stringify(latestBrowser,null,2)],{type:'application/json'}),'creator-browser-report.json');});
    $('release-save').addEventListener('click',()=>{
      if(latestRelease)download(new Blob([JSON.stringify(latestRelease,null,2)],{type:'application/json'}),'creator-release-report.json');
    });
    const syncFullstackModel=()=>{$('custom-model-fields').hidden=$('fullstack-model').value!=='custom';};
    const customFields=()=>{
      const lines=$('custom-fields').value.split(/\r?\n/).map(v=>v.trim()).filter(Boolean);
      if(!lines.length||lines.length>8)throw new Error('Custom models require 1 to 8 field lines.');
      return lines.map((line,index)=>{
        const parts=line.split('|').map(v=>v.trim()),type=(parts[1]||'').toLowerCase();
        if(!parts[0]||parts[0].length>80||!['text','integer','choice','link','stage'].includes(type))throw new Error('Use: Label | text, integer, link, choice or stage.');
        const field={id:'field'+(index+1),label:parts[0],type};
        if(type==='choice'||type==='stage'){
          if(parts.length!==3)throw new Error('Choice fields need a third part with comma-separated options.');
          const choices=parts[2].split(',').map(v=>v.trim()).filter(Boolean);
          if(choices.length<(type==='stage'?2:1)||choices.length>12||new Set(choices).size!==choices.length||choices.some(v=>v.length>80))throw new Error('Choice fields need 1 to 12 unique options.');
          field.choices=choices;
        }else if(parts.length!==2)throw new Error('Non-choice fields use exactly: Label | type.');
        return field;
      });
    };
    $('fullstack-model').addEventListener('change',syncFullstackModel);syncFullstackModel();
    $('fullstack-export').addEventListener('click',()=>run(async()=>{
      status('Building local database app…');
      const model=$('fullstack-model').value,payload={title:project.title,description:project.description,model};
      if(model==='custom')payload.fields=customFields();
      const r=await request('/api/fullstack-export',payload);download(await r.blob(),'local-data-workspace.zip');
      status('Local database app exported. Run server.py in the extracted folder.');
    }));
    window.initRelationalDesigner({
      example:{"version":1,"tables":[{"id":"categories","label":"Categories","fields":[{"id":"name","label":"Name","type":"text"}]},{"id":"items","label":"Items","fields":[{"id":"name","label":"Name","type":"text"},{"id":"quantity","label":"Quantity","type":"integer"},{"id":"state","label":"State","type":"choice","choices":["Available","Archived"]},{"id":"category","label":"Category","type":"relation","target":"categories"}]}]},
      validate:async schema=>(await (await request('/api/relational-validate',{schema})).json()).schema,
      download,
      onChange:()=>invalidateRelationalCheck()
    });
    $('relational-check-panel').hidden=!session.browser_checks_enabled;
    let relationalReport=null,reportRevision=0;
    invalidateRelationalCheck=()=>{
      reportRevision++;relationalReport=null;$('relational-check-save').disabled=true;
      $('relational-check-result').textContent='';
      $('relational-check-status').textContent='Application changed. Run a new check.';
    };
    $('relational-check-engine').addEventListener('change',invalidateRelationalCheck);
    const relationalInput=()=>({title:project.title,description:project.description,schema:JSON.parse($('relational-schema').value),engine:$('relational-check-engine').value,confirmed:true});
    $('relational-check').addEventListener('click',()=>run(async()=>{
      if(!session.browser_checks_enabled)return;
      if(!confirm('Test a fresh temporary application using synthetic records in the selected installed browser?'))return;
      invalidateRelationalCheck();const revision=reportRevision;
      $('relational-check').disabled=true;$('relational-check-status').textContent='Running isolated application checks…';
      try{
        const input=relationalInput();
        const result=await(await request('/api/relational-check',input)).json();
        if(revision!==reportRevision||JSON.stringify(input)!==JSON.stringify(relationalInput()))return;
        relationalReport=result;$('relational-check-save').disabled=false;
        $('relational-check-status').textContent=result.status==='passed'?'Passed — fresh synthetic-data application check.':'Failed — review diagnostics and installed browser.';
        $('relational-check-result').textContent=JSON.stringify(result,null,2);
      }catch(error){
        if(revision===reportRevision)$('relational-check-status').textContent='Check failed. Verify the schema and installed browser.';
        throw error;
      }finally{$('relational-check').disabled=false;}
    }));
    $('relational-check-save').addEventListener('click',()=>{
      if(relationalReport)download(new Blob([JSON.stringify(relationalReport,null,2)],{type:'application/json'}),'relational-report.json');
    });
    $('relational-export').addEventListener('click',()=>run(async()=>{
      const schema=JSON.parse($('relational-schema').value);
      status('Building relational database app…');
      const r=await request('/api/relational-export',{title:project.title,description:project.description,schema});
      download(await r.blob(),'local-relational-workspace.zip');
      status('Relational database app exported. Run server.py in the extracted folder.');
    }));
    status('Ready.');$('preview').click();
  }catch(e){status('Unable to load studio: '+e.message);}
}
start();
