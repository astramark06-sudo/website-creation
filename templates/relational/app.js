'use strict';
const $=id=>document.getElementById(id);
let token, schema, selected, editId=null, busy=false, data=null;
const controls=new Map();
function status(value){$('status').textContent=value;}
async function api(path,payload){
  const headers={'X-Workspace-Token':token||''};
  if(payload)headers['Content-Type']='application/json';
  const response=await fetch(path,{headers,method:payload?'POST':'GET',body:payload?JSON.stringify(payload):undefined});
  const result=await response.json();if(!response.ok)throw new Error(result.error);return result;
}
function option(select,value,label){
  const element=document.createElement('option');element.value=String(value);element.textContent=label;select.append(element);
}
function definition(){return schema.tables.find(t=>t.id===selected);}
function lock(value){
  document.querySelectorAll('button,input,select').forEach(el=>{el.disabled=value;});
  if(!value&&!data){$('submit').disabled=true;$('clear').disabled=true;}
}
function buildEditor(){
  editId=null;controls.clear();$('fields').replaceChildren();$('submit').textContent='Add record';
  for(const field of definition().fields){
    const label=document.createElement('label');label.textContent=field.label;
    const input=document.createElement(['choice','relation'].includes(field.type)?'select':'input');
    input.id='field-'+field.id;label.htmlFor=input.id;input.setAttribute('aria-label',field.label);
    if(field.type==='integer'){input.type='number';input.min='0';input.max='1000000';input.step='1';input.value='0';input.required=true;}
    if(field.type==='text'){input.type='text';input.maxLength=160;}
    if(field.type==='choice')field.choices.forEach(choice=>option(input,choice,choice));
    if(field.type==='relation'){
      option(input,'','No related record');
      for(const item of data.options[field.target]||[])option(input,item.id,item.label);
    }
    controls.set(field.id,input);label.append(input);$('fields').append(label);
  }
}
function button(parent,label,fn){
  const b=document.createElement('button');b.type='button';b.textContent=label;b.addEventListener('click',fn);parent.append(b);
}
function render(){
  $('records').replaceChildren();$('record-heading').textContent=definition().label+' records';
  for(const item of data.records){
    const li=document.createElement('li'),h=document.createElement('h3'),dl=document.createElement('dl');
    h.textContent='Record #'+item.id;li.append(h,dl);
    for(const field of definition().fields){
      const dt=document.createElement('dt'),dd=document.createElement('dd'),value=item.values[field.id];dt.textContent=field.label;
      dd.textContent=field.type==='relation'?(value===null?'None':(data.options[field.target]||[]).find(o=>o.id===value)?.label||'Record #'+value):String(value);
      dl.append(dt,dd);
    }
    button(li,'Edit',()=>{if(busy)return;editId=item.id;for(const field of definition().fields)controls.get(field.id).value=item.values[field.id]===null?'':String(item.values[field.id]);$('submit').textContent='Save record';controls.values().next().value.focus();});
    button(li,'Delete',()=>{if(!busy&&confirm('Delete this record? References in other tables will be cleared.'))run(async()=>{await api('/api/records',{action:'delete',table:selected,id:item.id});await refresh();});});
    $('records').append(li);
  }
  status(data.records.length+' records in '+definition().label+'.');
}
async function refresh(){
  data=null;$('records').replaceChildren();$('fields').replaceChildren();
  const response=await api('/api/records?'+new URLSearchParams({table:selected}));
  data=response;buildEditor();render();
}
async function run(fn){
  if(busy)return;busy=true;lock(true);
  try{await fn();}catch(error){status(error.message||'Request failed.');}
  finally{busy=false;lock(false);}
}
async function start(){
  try{
    const session=await api('/api/session');token=session.token;schema=session.config.schema;
    $('title').textContent=session.config.title;$('description').textContent=session.config.description;document.title=session.config.title;
    for(const table of schema.tables)option($('table'),table.id,table.label);
    selected=schema.tables[0].id;$('table').value=selected;
    $('table').addEventListener('change',()=>{selected=$('table').value;run(refresh);});
    $('clear').addEventListener('click',()=>{if(!busy&&data)buildEditor();});
    $('editor').addEventListener('submit',event=>{
      event.preventDefault();if(busy||!data)return;
      const values=Object.create(null);
      for(const field of definition().fields){
        const v=controls.get(field.id).value;
        values[field.id]=field.type==='integer'?Number(v):field.type==='relation'?(v?Number(v):null):v;
      }
      const payload={action:editId===null?'add':'edit',table:selected,values};if(editId!==null)payload.id=editId;
      run(async()=>{await api('/api/records',payload);await refresh();});
    });
    await run(refresh);
  }catch(error){status(error.message||'Unable to initialize workspace.');}
}
start();
