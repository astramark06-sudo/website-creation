'use strict';
// Locally decode bounded PNG/JPEG images; only four coarse categories leave the browser.
(() => {
  const MAX_FILE=8*1024*1024, MAX_PIXELS=16000000, SAMPLE=96;
  function classify(pixels,w,h){
    let light=0,warm=0,cool=0,neutral=0,edges=0,comparisons=0;
    const luminance=new Float32Array(SAMPLE*SAMPLE);
    for(let i=0;i<luminance.length;i++){
      const j=i*4, alpha=pixels[j+3]/255;
      const r=pixels[j]*alpha+255*(1-alpha),g=pixels[j+1]*alpha+255*(1-alpha),b=pixels[j+2]*alpha+255*(1-alpha);
      luminance[i]=.2126*r+.7152*g+.0722*b;light+=luminance[i];
      if(Math.max(r,g,b)-Math.min(r,g,b)<28)neutral++;
      else if(r>b+18)warm++;
      else if(b>r+18||g>r+18)cool++;
      else neutral++;
    }
    for(let y=0;y<SAMPLE;y++)for(let x=0;x<SAMPLE;x++){
      const i=y*SAMPLE+x;
      if(x>0){comparisons++;if(Math.abs(luminance[i]-luminance[i-1])>32)edges++;}
      if(y>0){comparisons++;if(Math.abs(luminance[i]-luminance[i-SAMPLE])>32)edges++;}
    }
    const family=neutral/luminance.length>.8?'neutral':warm>cool*1.6?'warm':cool>warm*1.6?'cool':'mixed';
    const score=edges/comparisons,average=light/luminance.length;
    return {shape:w/h>1.2?'landscape':h/w>1.2?'portrait':'square',
      palette_family:family,density:score<.04?'low':score>.16?'high':'medium',
      lightness:average>190?'light':average<90?'dark':'mixed'};
  }
  function dimensions(buffer){
    const d=new DataView(buffer), n=d.byteLength;
    if(n>=24&&d.getUint32(0)===0x89504e47&&d.getUint32(4)===0x0d0a1a0a&&d.getUint32(12)===0x49484452){
      return {w:d.getUint32(16),h:d.getUint32(20),type:'image/png'};
    }
    if(n>=4&&d.getUint16(0)===0xffd8){
      let i=2;
      while(i+4<=n){
        if(d.getUint8(i++)!==255)break;
        while(i<n&&d.getUint8(i)===255)i++;
        if(i>=n)break;
        const marker=d.getUint8(i++);
        if(marker===0xda||marker===0xd9||i+2>n)break;
        const length=d.getUint16(i);
        if(length<2||i+length>n)break;
        if([0xc0,0xc1,0xc2].includes(marker)&&length>=8)
          return {w:d.getUint16(i+5),h:d.getUint16(i+3),type:'image/jpeg'};
        i+=length;
      }
    }
    throw new Error('Choose a valid PNG or JPEG screenshot.');
  }
  async function analyze(file){
    if(!file||file.size<=0||file.size>MAX_FILE)throw new Error('Choose a PNG or JPEG up to 8 MiB.');
    const buffer=await file.arrayBuffer();
    const size=dimensions(buffer);
    if(!size.w||!size.h||size.w>8192||size.h>8192||size.w*size.h>MAX_PIXELS)
      throw new Error('Screenshot exceeds the 16-megapixel or 8192-pixel dimension limit.');
    const bitmap=await createImageBitmap(new Blob([buffer],{type:size.type}),{resizeWidth:SAMPLE,resizeHeight:SAMPLE,resizeQuality:'low'});
    try{
      const canvas=document.createElement('canvas');canvas.width=SAMPLE;canvas.height=SAMPLE;
      const ctx=canvas.getContext('2d',{willReadFrequently:true});
      if(!ctx)throw new Error('Local image analysis unavailable.');
      ctx.drawImage(bitmap,0,0,SAMPLE,SAMPLE);
      return classify(ctx.getImageData(0,0,SAMPLE,SAMPLE).data,size.w,size.h);
    }finally{bitmap.close();}
  }
  window.analyzeVisualReference=analyze;
})();
