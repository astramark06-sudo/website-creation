'use strict';
(() => {
  const $=id=>document.getElementById(id);
  const copy=value=>JSON.parse(JSON.stringify(value));
  function control(parent,label,value,onChange,options){
    const wrap=document.createElement('label');wrap.textContent=label;
    const input=document.createElement(options?.choices?'select':options?.multiline?'textarea':'input');
    input.setAttribute('aria-label',label);
    if(options?.choices)for(const item of options.choices){
      const option=document.createElement('option');option.value=item.value;option.textContent=item.label;input.append(option);
    }
    if(options?.max)input.maxLength=options.max;
    if(options?.multiline)input.rows=3;
    input.value=value;input.addEventListener(options?.choices?'change':'input',()=>onChange(input.value));
    wrap.append(input);parent.append(wrap);return input;
  }
  function button(parent,label,fn,disabled=false){
    const b=document.createElement('button');b.type='button';b.textContent=label;b.disabled=disabled;
    b.addEventListener('click',fn);parent.append(b);return b;
  }
  function note(parent,text){const p=document.createElement('p');p.className='relational-id';p.textContent=text;parent.append(p);}
  function container(parent,legend,cls){
    const block=document.createElement('fieldset');block.className=cls;
    const title=document.createElement('legend');title.textContent=legend;block.append(title);parent.append(block);return block;
  }
  window.initRelationalDesigner=({example,validate,download})=>{
    let schema=null,manual=false,pending=false,revision=0,nextTable=1,nextField=1;
    const raw=$('relational-schema'),visual=$('relational-visual'),host=$('relational-tables'),add=$('relational-add-table');
    const say=text=>{$('relational-design-status').textContent=text;};
    const kinds=['text','integer','choice','relation'].map(value=>({value,label:value}));
    function allocate(prefix,used){
      let id;
      do{id=prefix+(prefix==='table'?nextTable++:nextField++);}while(used.has(id));
      return id;
    }
    function newField(table){
      return {id:allocate('field',new Set(table.fields.map(f=>f.id))),label:'Name',type:'text'};
    }
    function newTable(){
      const table={id:allocate('table',new Set(schema.tables.map(t=>t.id))),label:'New table',fields:[]};
      table.fields.push(newField(table));return table;
    }
    function write(message='Schema updated. Export will validate all fields.'){
      revision++;
      raw.value=JSON.stringify(schema,null,2);
      // The backend checks UTF-8 length and the complete schema at export.
      say(message);
    }
    function replaceSchema(value){
      schema=copy(value);manual=false;raw.removeAttribute('aria-invalid');visual.hidden=false;
      write('Schema ready. Edit tables and fields below.');render();
    }
    function replaceAllowed(){
      return !manual||confirm('Replace the unapplied JSON edits?');
    }
    function render(focusId){
      host.replaceChildren();add.disabled=schema.tables.length>=4;
      schema.tables.forEach((table,i)=>{
        const t=container(host,'Table '+(i+1),'relational-table');
        t.dataset.tableId=table.id;
        note(t,'Table ID: '+table.id);
        const tableLabel=control(t,'Table label',table.label,v=>{
          table.label=v;write();
          // Update relation option labels without rebuilding the focused input.
          for(const option of host.querySelectorAll('select[data-relation] option')){
            if(option.value===table.id)option.textContent=(v||'Untitled')+' ('+table.id+')';
          }
        },{max:80});
        tableLabel.id='rel-table-'+table.id;
        const actions=document.createElement('div');actions.className='actions';t.append(actions);
        button(actions,'Remove table',()=>{
          if(schema.tables.some(other=>other.id!==table.id&&other.fields.some(f=>f.type==='relation'&&f.target===table.id))){
            say('Remove or change relationships targeting '+(table.label||table.id)+' before removing this table.');return;
          }
          schema.tables=schema.tables.filter(x=>x!==table);write();render('relational-add-table');
        },schema.tables.length<=2);
        table.fields.forEach((field,j)=>{
          const block=container(t,'Field '+(j+1),'relational-field');block.dataset.fieldId=field.id;
          note(block,'Field ID: '+field.id);
          const fieldLabel=control(block,'Field label',field.label,v=>{field.label=v;write();},{max:80});
          fieldLabel.id='rel-field-'+table.id+'-'+field.id;
          control(block,'Field type',field.type,v=>{
            field.type=v;delete field.choices;delete field.target;
            if(v==='choice')field.choices=['Option 1','Option 2'];
            if(v==='relation')field.target=schema.tables.find(other=>other.id!==table.id).id;
            write();render('rel-type-'+table.id+'-'+field.id);
          },{choices:kinds}).id='rel-type-'+table.id+'-'+field.id;
          if(field.type==='choice'){
            control(block,'Choice options (one per line)',field.choices.join('\n'),v=>{
              field.choices=v.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);write();
            },{multiline:true,max:1200});
          }
          if(field.type==='relation'){
            const choices=schema.tables.filter(x=>x.id!==table.id).map(x=>({value:x.id,label:(x.label||'Untitled')+' ('+x.id+')'}));
            const relation=control(block,'Related table',field.target,v=>{field.target=v;write();},{choices});
            relation.dataset.relation='true';
          }
          button(block,'Remove field',()=>{
            table.fields=table.fields.filter(x=>x!==field);write();render('rel-add-'+table.id);
          },table.fields.length<=1);
        });
        button(t,'Add field',()=>{
          const field=newField(table);table.fields.push(field);write();render('rel-field-'+table.id+'-'+field.id);
        },table.fields.length>=8).id='rel-add-'+table.id;
      });
      if(focusId)$(focusId)?.focus();
    }
    add.addEventListener('click',()=>{
      if(!schema||manual||schema.tables.length>=4)return;
      const table=newTable();schema.tables.push(table);write();render('rel-table-'+table.id);
    });
    $('relational-new').addEventListener('click',()=>{
      if(!replaceAllowed())return;
      schema={version:1,tables:[]};schema.tables.push(newTable(),newTable());replaceSchema(schema);
    });
    $('relational-example').addEventListener('click',()=>{if(replaceAllowed())replaceSchema(example);});
    raw.addEventListener('input',()=>{
      revision++;manual=true;visual.hidden=true;raw.removeAttribute('aria-invalid');
      say('JSON edited. Validate and apply it to resume visual editing.');
    });
    $('relational-apply-json').addEventListener('click',async()=>{
      if(pending)return;
      pending=true;const current=revision;$('relational-apply-json').disabled=true;
      try{
        const value=await validate(JSON.parse(raw.value));
        if(current!==revision)return;
        replaceSchema(value);
      }catch(error){
        if(current!==revision)return;
        raw.setAttribute('aria-invalid','true');
        say('Schema invalid. Check JSON syntax, field IDs, types, limits and relationship targets.');
      }finally{pending=false;$('relational-apply-json').disabled=false;}
    });
    $('relational-save-json').addEventListener('click',async()=>{
      if(pending)return;
      pending=true;const current=revision;$('relational-save-json').disabled=true;
      try{
        const value=await validate(JSON.parse(raw.value));
        if(current!==revision)return;
        download(new Blob([JSON.stringify(value)],{type:'application/json'}),'relational-schema.json');
        say('Validated schema download requested.');
      }catch(error){if(current===revision)say('Schema invalid. Correct the schema before downloading.');}
      finally{pending=false;$('relational-save-json').disabled=false;}
    });
  };
})();
