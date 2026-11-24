'use strict';
const $=id=>document.getElementById(id);
let token, editId=null, busy=false, fields=[], linkOptions=[];
const controls=new Map();
const status=message=>{$('status').textContent=message;};
async function api(path,payload){
  const headers={'X-Workspace-Token':token||''};
  if(payload)headers['Content-Type']='application/json';
  const r=await fetch(path,{method:payload?'POST':'GET',headers,body:payload?JSON.stringify(payload):undefined});
  const data=await r.json();
  if(!r.ok)throw new Error(data.error);
  return data;
}
function populateLinks(skipId=null){
  for(const field of fields.filter(f=>f.type==='link')){
    const select=controls.get(field.id), prior=select.value;
    select.replaceChildren();
    const empty=document.createElement('option');empty.value='';empty.textContent='No linked record';select.append(empty);
    for(const item of linkOptions){
      if(item.id===skipId)continue;
      const option=document.createElement('option');option.value=String(item.id);option.textContent=item.title;select.append(option);
    }
    if([...select.options].some(o=>o.value===prior))select.value=prior;
  }
}
function clear(){editId=null;$('editor').reset();populateLinks();$('submit').textContent='Add record';}
function setupFields(){
  for(const field of fields){
    const label=document.createElement('label');label.textContent=field.label;
    const input=document.createElement(['choice','link','stage'].includes(field.type)?'select':'input');
    input.id='model-'+field.id;
    if(field.type==='choice'||field.type==='stage')for(const choice of field.choices){const option=document.createElement('option');option.value=choice;option.textContent=choice;input.append(option);}
    if(field.type==='stage'){input.disabled=true;const stageFilter=$('stage-filter');for(const choice of field.choices){const option=document.createElement('option');option.value=choice;option.textContent=choice;stageFilter.append(option);}$('stage-filter-label').hidden=false;}
    if(field.type==='integer'){input.type='number';input.min='0';input.max='1000000';input.step='1';input.required=true;input.defaultValue='0';}
    if(field.type==='text'){input.type='text';input.maxLength=160;}
    controls.set(field.id,input);label.append(input);$('model-fields').append(label);
  }
}
function detailsForSave(){
  const values=Object.create(null);
  for(const f of fields){
    const c=controls.get(f.id);
    values[f.id]=f.type==='integer'?Number(c.value):f.type==='link'?(c.value?Number(c.value):null):c.value;
  }
  return values;
}
function button(parent,text,fn){const b=document.createElement('button');b.type='button';b.textContent=text;b.addEventListener('click',fn);parent.append(b);}
function metricPair(parent,label,value){
  const pair=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');
  dt.textContent=label;dd.textContent=String(value);pair.append(dt,dd);parent.append(pair);
}
function renderAnalytics(summary){
  const counts=$('analytics-counts');counts.replaceChildren();
  metricPair(counts,'Matching records',summary.total);
  metricPair(counts,'Open records',summary.open);
  metricPair(counts,'Completed records',summary.completed);
  const percent=summary.completion_percent,meter=$('completion-meter');
  meter.hidden=percent===null;meter.value=percent===null?0:percent;
  $('completion-caption').textContent=percent===null?'No matching records to summarize.':percent+'% completed.';
  const host=$('analytics-fields');host.replaceChildren();
  for(const field of summary.fields){
    const group=document.createElement('div'),heading=document.createElement('h4'),dl=document.createElement('dl');
    group.className='analytics-field';heading.textContent=field.label;dl.className='analytics-grid';
    if(field.type==='integer'){
      metricPair(dl,'Total',field.total);metricPair(dl,'Average',field.average===null?'Not applicable':field.average);
    }else if(field.type==='choice'||field.type==='stage'){
      for(const choice of field.choices)metricPair(dl,choice.label,choice.count);
    }else if(field.type==='link'){
      metricPair(dl,'Linked records',field.linked);metricPair(dl,'Without link',summary.total-field.linked);
    }
    group.append(heading,dl);host.append(group);
  }
  $('analytics').hidden=false;
}
async function refresh(){
  const q=new URLSearchParams({q:$('search').value,state:$('filter').value});
  if($('stage-filter').value)q.set('stage',$('stage-filter').value);
  const data=await api('/api/items?'+q);renderAnalytics(data.summary);$('items').replaceChildren();linkOptions=data.link_options||[];populateLinks(editId);
  for(const item of data.items){
    const li=document.createElement('li'),h=document.createElement('h3'),p=document.createElement('p');
    h.textContent=item.title;p.textContent=item.notes;if(item.done)h.className='completed';li.append(h,p);
    if(fields.length){
      const dl=document.createElement('dl');
      for(const f of fields){
        const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=f.label;
        dd.textContent=f.type==='link'?(item.links?.[f.id]?.title||'None'):String(item.details[f.id]);
        dl.append(dt,dd);
      }
      li.append(dl);
    }
    button(li,'Edit',()=>{
      editId=item.id;$('name').value=item.title;$('notes').value=item.notes;populateLinks(item.id);
      for(const f of fields)controls.get(f.id).value=f.type==='link'?(item.details[f.id]===null?'':String(item.details[f.id])):String(item.details[f.id]);
      $('submit').textContent='Save record';$('name').focus();
    });
    const workflow=fields.find(f=>f.type==='stage');
    if(workflow){
      const current=item.details[workflow.id],index=workflow.choices.indexOf(current);
      for(const [label,offset] of [['Previous stage',-1],['Next stage',1]]){
        const target=workflow.choices[index+offset];
        if(target===undefined)continue;
        button(li,label+': '+target,()=>run(async()=>{
          await api('/api/items',{action:'move_stage',id:item.id,expected:current,target});
          if(editId===item.id)clear();
          await refresh();
        }));
      }
    }
    button(li,item.done?'Reopen':'Complete',()=>run(async()=>{await api('/api/items',{action:'toggle',id:item.id});await refresh();}));
    button(li,'Delete',()=>{if(confirm('Delete this record?'))run(async()=>{await api('/api/items',{action:'delete',id:item.id});if(editId===item.id)clear();await refresh();});});
    $('items').append(li);
  }
  status(data.items.length+' matching records.');
}
async function run(fn){if(busy)return;busy=true;try{await fn();}catch(e){status(e.message||'Request failed');}finally{busy=false;}}
async function start(){try{
  const session=await api('/api/session');token=session.token;$('title').textContent=session.config.title;$('description').textContent=session.config.description;fields=session.config.fields||[];setupFields();
  $('editor').addEventListener('submit',e=>{e.preventDefault();run(async()=>{const data={action:editId===null?'add':'edit',title:$('name').value,notes:$('notes').value};if(editId!==null)data.id=editId;if(fields.length)data.details=detailsForSave();await api('/api/items',data);clear();await refresh();});});
  $('filters').addEventListener('submit',e=>{e.preventDefault();run(refresh);});
  $('cancel').addEventListener('click',clear);
  await refresh();
}catch(e){status(e.message);}}
start();
