const button=document.getElementById('load-recording');
const status=document.getElementById('status');
const player=document.getElementById('recording-player');
const download=document.getElementById('download');
const digest=async b=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',b))).map(x=>x.toString(16).padStart(2,'0')).join('');
button.addEventListener('click',async()=>{
 button.disabled=true;
 try{
  const response=await fetch('recording-download.json');if(!response.ok)throw Error('Recording index is unavailable.');
  const manifest=await response.json();const blocks=[];let total=0;
  for(const [i,part] of manifest.parts.entries()){
   status.textContent=`Loading recording: part ${i+1} of ${manifest.parts.length}...`;
   const r=await fetch(part.path);if(!r.ok)throw Error('Recording data is unavailable.');
   const b=await r.arrayBuffer();if(b.byteLength!==part.bytes||await digest(b)!==part.sha256)throw Error('Recording data failed the integrity check.');
   blocks.push(b);total+=b.byteLength;
  }
  const blob=new Blob(blocks,{type:'video/mp4'});
  if(total!==manifest.bytes||await digest(await blob.arrayBuffer())!==manifest.sha256)throw Error('The full recording failed the integrity check.');
  const url=URL.createObjectURL(blob);player.src=url;player.hidden=false;download.href=url;download.download=manifest.filename;download.hidden=false;
  status.textContent='File integrity verified. Use the video controls to play the recording or download it.';
  document.documentElement.dataset.recordingVerified=manifest.sha256;button.hidden=true;
 }catch(e){status.textContent=e.message+' Please retry.';button.disabled=false;}
});