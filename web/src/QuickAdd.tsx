import {useRef,useState} from 'react';
import {useCurrency} from './Currency';
import {DraftCard} from './DraftCard';
import {prepareDocumentPhoto} from './format';
import {parseRecordSentence} from './recordParser';
import type {Draft,Profile} from './types';

type Props={request:<T>(path:string,body?:unknown)=>Promise<T>;revision:string;onSaved:()=>Promise<void>|void;profile:Profile|null;cloudAvailable:boolean};

/** The fast way to add records: photograph a bill or receipt, or just type or say what happened. */
export function QuickAdd({request,revision,onSaved,profile,cloudAvailable}:Props){
  const {currency,digits}=useCurrency();
  const [text,setText]=useState('');const [busy,setBusy]=useState<''|'photo'|'text'>('');const [error,setError]=useState('');
  const [draft,setDraft]=useState<Draft|null>(null);const [preview,setPreview]=useState('');
  const file=useRef<HTMLInputElement>(null);
  const smart=!!profile?.smart_assist&&cloudAvailable;
  async function scan(f:File|undefined){
    if(!f)return;setError('');setDraft(null);setBusy('photo');
    try{
      const image=await prepareDocumentPhoto(f);setPreview(image);
      const r=await request<{draft:Draft}>('/assist/scan',{image});
      if(!r.draft.ok)setError('I could not read a bill or receipt in that photo. Try a clearer, well-lit picture, or type it instead.');
      else setDraft(r.draft);
    }catch(e){setError(e instanceof Error?e.message:'The photo could not be read.');}
    finally{setBusy('');if(file.current)file.current.value='';}
  }
  async function read(){
    const sentence=text.trim();if(!sentence)return;setError('');setDraft(null);setBusy('text');
    try{
      const local=parseRecordSentence(sentence,{currency,digits});
      if(local){setDraft(local);return;}
      if(!smart)throw new Error('I could not understand that. Try something like "I paid Rahman 5000 for freight yesterday".');
      const r=await request<{draft:Draft}>('/assist/extract',{text:sentence});
      if(!r.draft.ok)throw new Error('I could not find an amount or a payment in that. Try something like "I paid Rahman 5000 for freight yesterday".');
      setDraft(r.draft);
    }catch(e){setError(e instanceof Error?e.message:'Could not read that.');}
    finally{setBusy('');}
  }
  return <section className="panel quick-add" aria-labelledby="quick-add-title">
    <div className="panel-heading"><div><p className="eyebrow">THE FAST WAY</p><h2 id="quick-add-title">Add by photo or by typing</h2></div></div>
    <div className="quick-grid">
      <div className="quick-box">
        <h3>📷 Photograph a bill or receipt</h3>
        <p className="small muted">We read the supplier, date, amount and due date. You check it before anything is saved.</p>
        <input ref={file} id="document-photo" type="file" accept="image/*" capture="environment" hidden onChange={e=>void scan(e.target.files?.[0])}/>
        <button disabled={busy!==''||!smart} onClick={()=>file.current?.click()}>{busy==='photo'?'Reading your photo…':'Take or choose a photo'}</button>
        {!smart&&<p className="small muted">{profile&&!profile.smart_assist?'Turn on Smart assist in Settings to read photos.':'Photo reading is not available right now.'}</p>}
        {preview&&busy==='photo'&&<img className="scan-preview" src={preview} alt="Your photo being read"/>}
      </div>
      <div className="quick-box">
        <h3>✍️ Type it like a message</h3>
        <label htmlFor="quick-text" className="sr-only">Describe the payment or bill</label>
        <textarea id="quick-text" rows={3} maxLength={400} value={text} onChange={e=>setText(e.target.value)} placeholder={'e.g. "I paid Rahman 5000 for freight yesterday"\n"Received 20,000 from Karim Traders"\n"Bill from Dhaka Packaging 12000 due in 10 days"'}/>
        <button disabled={busy!==''||!text.trim()} onClick={()=>void read()}>{busy==='text'?'Reading…':'Read it'}</button>
      </div>
    </div>
    {error&&<p className="error" role="alert">{error}</p>}
    {draft&&<DraftCard key={JSON.stringify(draft)} draft={draft} revision={revision} request={request} onDiscard={()=>{setDraft(null);setPreview('');}} onSaved={async()=>{await onSaved();setText('');setPreview('');}}/>}
  </section>;
}
