export const prettyVendor=(id:string)=>id.replace(/[-_.:]+/g,' ').replace(/\s+/g,' ').trim().replace(/\b\w/g,c=>c.toUpperCase());
export const initials=(name:string)=>{const parts=name.trim().split(/\s+/).filter(Boolean);return ((parts[0]?.[0]||'')+(parts.length>1?parts[parts.length-1][0]:'')).toUpperCase()||'?';};
import {t} from './i18n';
const locale=()=>{const l=document.documentElement.lang;return l&&l!=='en'?l:undefined;};
export const workspaceLabel=(name:string)=>name==='My workspace'?t('My workspace'):name;
export const formatTime=(ts:number)=>new Date(ts*1000).toLocaleString(locale(),{dateStyle:'medium',timeStyle:'short'});
export const formatDate=(iso:string)=>{const d=new Date(iso+'T00:00:00');return Number.isNaN(d.getTime())?iso:d.toLocaleDateString(locale(),{day:'numeric',month:'short',year:'numeric'});};
export const todayIso=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;};

async function loadBitmap(file:File):Promise<ImageBitmap>{
  if(!/^image\/(jpeg|png|webp|heic|heif)$/i.test(file.type)&&!/\.(jpe?g|png|webp)$/i.test(file.name))throw new Error('Use a JPG, PNG or WebP photo.');
  try{return await createImageBitmap(file);}catch{throw new Error('That picture could not be opened. Try a JPG or PNG.');}
}
function toJpeg(bitmap:ImageBitmap,width:number,height:number,quality:number):string{
  const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;
  const ctx=canvas.getContext('2d');if(!ctx)throw new Error('This browser cannot prepare the picture.');
  ctx.fillStyle='#fff';ctx.fillRect(0,0,width,height);ctx.drawImage(bitmap,0,0,width,height);
  return canvas.toDataURL('image/jpeg',quality);
}
const bytesOf=(dataUrl:string)=>Math.floor((dataUrl.length-dataUrl.indexOf(',')-1)*3/4);

/** Shrinks a document photo so it uploads fast and stays under the server limit, keeping text readable. */
export async function prepareDocumentPhoto(file:File,maxSide=1800,maxBytes=1_000_000):Promise<string>{
  const bitmap=await loadBitmap(file);
  let scale=Math.min(1,maxSide/Math.max(bitmap.width,bitmap.height));
  for(let attempt=0;attempt<6;attempt++){
    const w=Math.max(1,Math.round(bitmap.width*scale)),h=Math.max(1,Math.round(bitmap.height*scale));
    for(const q of [0.85,0.72,0.6]){const url=toJpeg(bitmap,w,h,q);if(bytesOf(url)<=maxBytes){bitmap.close();return url;}}
    scale*=0.8;
  }
  bitmap.close();throw new Error('That photo is too large. Try a smaller picture.');
}

/** Centre-crops to a small square for the profile picture. */
export async function prepareAvatar(file:File,size=256):Promise<string>{
  const bitmap=await loadBitmap(file);
  const side=Math.min(bitmap.width,bitmap.height);
  const canvas=document.createElement('canvas');canvas.width=size;canvas.height=size;
  const ctx=canvas.getContext('2d');if(!ctx)throw new Error('This browser cannot prepare the picture.');
  ctx.drawImage(bitmap,(bitmap.width-side)/2,(bitmap.height-side)/2,side,side,0,0,size,size);bitmap.close();
  for(const q of [0.9,0.8,0.7,0.6]){const url=canvas.toDataURL('image/jpeg',q);if(bytesOf(url)<=150_000)return url;}
  throw new Error('That picture is too detailed. Try another one.');
}
