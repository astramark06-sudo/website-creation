'use strict';
const $=id=>document.getElementById(id);
let token, editId=null, busy=false;
const status=message=>{$('status').textContent=message;};
async function api(path,payload){
  const headers={'X-Workspace-Token':token||''};
  if(payload)headers['Content-Type']='application/json';
  const r=await fetch(path,{method:payload?'POST':'GET',headers,body:payload?JSON.stringify(payload):undefined});
  const data=await r.json();
  if(!r.ok)throw new Error(data.error);
  return data;
}
function clear(){editId=null;$('name').value='';$('notes').value='';$('submit').textContent='Add record';}
function button(parent,text,fn){const b=document.createElement('button');b.type='button';b.textContent=text;b.addEventListener('click',fn);parent.append(b);}
async function refresh(){
  const q=new URLSearchParams({q:$('search').value,state:$('filter').value});
  const data=await api('/api/items?'+q);$('items').replaceChildren();
  for(const item of data.items){
    const li=document.createElement('li'),h=document.createElement('h3'),p=document.createElement('p');
    h.textContent=item.title;p.textContent=item.notes;if(item.done)h.className='completed';li.append(h,p);
    button(li,'Edit',()=>{editId=item.id;$('name').value=item.title;$('notes').value=item.notes;$('submit').textContent='Save record';$('name').focus();});
    button(li,item.done?'Reopen':'Complete',()=>run(async()=>{await api('/api/items',{action:'toggle',id:item.id});await refresh();}));
    button(li,'Delete',()=>{if(confirm('Delete this record?'))run(async()=>{await api('/api/items',{action:'delete',id:item.id});if(editId===item.id)clear();await refresh();});});
    $('items').append(li);
  }
  status(data.items.length+' matching records.');
}
async function run(fn){if(busy)return;busy=true;try{await fn();}catch(e){status(e.message||'Request failed');}finally{busy=false;}}
async function start(){try{
  const session=await api('/api/session');token=session.token;$('title').textContent=session.config.title;$('description').textContent=session.config.description;
  $('editor').addEventListener('submit',e=>{e.preventDefault();run(async()=>{const data={action:editId===null?'add':'edit',title:$('name').value,notes:$('notes').value};if(editId!==null)data.id=editId;await api('/api/items',data);clear();await refresh();});});
  $('filters').addEventListener('submit',e=>{e.preventDefault();run(refresh);});
  $('cancel').addEventListener('click',clear);
  await refresh();
}catch(e){status(e.message);}}
start();
