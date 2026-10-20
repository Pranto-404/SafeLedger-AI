import {createContext,useCallback,useContext,useEffect,useMemo,useRef,useState,type ReactNode} from 'react';

export type Language={code:string;name:string;rtl:boolean};
/** Same list as the server. English is always the source text; other languages are translated once on the server and cached. */
export const LANGUAGES:Language[]=[
  {code:'en',name:'English',rtl:false},{code:'bn',name:'বাংলা',rtl:false},{code:'zh-CN',name:'简体中文',rtl:false},{code:'zh-TW',name:'繁體中文',rtl:false},
  {code:'ja',name:'日本語',rtl:false},{code:'ko',name:'한국어',rtl:false},{code:'hi',name:'हिन्दी',rtl:false},{code:'ur',name:'اردو',rtl:true},
  {code:'ar',name:'العربية',rtl:true},{code:'fa',name:'فارسی',rtl:true},{code:'he',name:'עברית',rtl:true},{code:'es',name:'Español',rtl:false},
  {code:'fr',name:'Français',rtl:false},{code:'pt',name:'Português',rtl:false},{code:'de',name:'Deutsch',rtl:false},{code:'it',name:'Italiano',rtl:false},
  {code:'ru',name:'Русский',rtl:false},{code:'tr',name:'Türkçe',rtl:false},{code:'id',name:'Bahasa Indonesia',rtl:false},{code:'ms',name:'Bahasa Melayu',rtl:false},
  {code:'th',name:'ไทย',rtl:false},{code:'vi',name:'Tiếng Việt',rtl:false},{code:'ta',name:'தமிழ்',rtl:false},{code:'te',name:'తెలుగు',rtl:false},
  {code:'mr',name:'मराठी',rtl:false},{code:'pa',name:'ਪੰਜਾਬੀ',rtl:false},{code:'gu',name:'ગુજરાતી',rtl:false},{code:'kn',name:'ಕನ್ನಡ',rtl:false},
  {code:'ml',name:'മലയാളം',rtl:false},{code:'ne',name:'नेपाली',rtl:false},{code:'si',name:'සිංහල',rtl:false},{code:'nl',name:'Nederlands',rtl:false},
  {code:'pl',name:'Polski',rtl:false},{code:'uk',name:'Українська',rtl:false},{code:'el',name:'Ελληνικά',rtl:false},{code:'sw',name:'Kiswahili',rtl:false},{code:'fil',name:'Filipino',rtl:false},
];
const STORE='capzoryx-lang';
let strings:Record<string,string>={};

/** Look a phrase up in the chosen language. Unknown phrases stay in English. {name} placeholders are filled from vars. */
export function t(text:string,vars?:Record<string,string|number>):string{
  let out=strings[text]??text;
  if(vars)out=out.replace(/\{(\w+)\}/g,(m,k)=>k in vars?String(vars[k]):m);
  return out;
}

type Cache={version:string;strings:Record<string,string>;missing:number};
const read=(code:string):Cache|null=>{try{const raw=localStorage.getItem('capzoryx-i18n-'+code);return raw?JSON.parse(raw) as Cache:null;}catch{return null;}};
const write=(code:string,value:Cache)=>{try{localStorage.setItem('capzoryx-i18n-'+code,JSON.stringify(value));}catch{/* optional */}};
export const hasChosenLanguage=()=>{try{return !!localStorage.getItem(STORE);}catch{return false;}};
const remembered=()=>{try{const c=localStorage.getItem(STORE);return c&&LANGUAGES.some(l=>l.code===c)?c:'en';}catch{return 'en';}};

type Ctx={code:string;busy:boolean;partial:boolean;rev:number;setLanguage:(code:string)=>void};
const I18nContext=createContext<Ctx>({code:'en',busy:false,partial:false,rev:0,setLanguage:()=>{}});
export const useI18n=()=>useContext(I18nContext);

export function I18nProvider({children}:{children:ReactNode}){
  const [code,setCode]=useState(remembered);const [busy,setBusy]=useState(false);const [partial,setPartial]=useState(false);const [rev,tick]=useState(0);
  const run=useRef(0);
  const apply=useCallback((next:string,value:Cache|null)=>{
    strings=value?.strings||{};
    const lang=LANGUAGES.find(l=>l.code===next);
    document.documentElement.lang=next;document.documentElement.dir=lang?.rtl?'rtl':'ltr';
    tick(n=>n+1);
  },[]);
  useEffect(()=>{
    const id=++run.current;
    if(code==='en'){apply('en',null);setBusy(false);setPartial(false);return;}
    const cached=read(code);apply(code,cached);setPartial(!cached||cached.missing>0);
    const controller=new AbortController();
    void (async()=>{
      setBusy(true);
      try{
        // Ready-made file from the site itself: instant, no server work. Anything newer is filled in by the server below.
        if(!cached){
          try{
            const f=await fetch('/locales/'+code+'.json',{signal:controller.signal});
            if(f.ok&&run.current===id){const file=await f.json() as {version:string;strings:Record<string,string>};if(file&&typeof file.strings==='object'){const value={version:file.version,strings:file.strings,missing:1};write(code,value);apply(code,value);}}
          }catch{/* the server path below still works */}
        }
        for(let round=0;round<10&&run.current===id;round++){
          const r=await fetch('/api/i18n?lang='+encodeURIComponent(code),{credentials:'same-origin',signal:controller.signal});
          if(!r.ok)break;
          const body=await r.json() as {strings:Record<string,string>;missing:number;version:string};
          if(run.current!==id)return;
          const value={version:body.version,strings:body.strings,missing:body.missing};
          write(code,value);apply(code,value);setPartial(body.missing>0);
          if(body.missing===0)break;
          await new Promise(res=>setTimeout(res,1500));
        }
      }catch{/* offline or aborted: keep what we have */}
      finally{if(run.current===id)setBusy(false);}
    })();
    return()=>controller.abort();
  },[code,apply]);
  const setLanguage=useCallback((next:string)=>{if(!LANGUAGES.some(l=>l.code===next))return;try{localStorage.setItem(STORE,next);}catch{/* optional */}setCode(next);},[]);
  const value=useMemo(()=>({code,busy,partial,rev,setLanguage}),[code,busy,partial,rev,setLanguage]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function LanguagePicker({id='language',compact=false,onPicked}:{id?:string;compact?:boolean;onPicked?:(code:string)=>void}){
  const {code,busy,partial,setLanguage}=useI18n();
  return <div className={compact?'language-picker compact':'language-picker'}>
    <label htmlFor={id} className={compact?'sr-only':undefined}>{t('Language')}</label>
    <select id={id} value={code} onChange={e=>{setLanguage(e.target.value);onPicked?.(e.target.value);}} aria-label={t('Language')}>{LANGUAGES.map(l=><option key={l.code} value={l.code}>{l.name}</option>)}</select>
    {busy&&partial&&<small className="muted" role="status">{t('Translating…')}</small>}
  </div>;
}

/** Marks a phrase for translation without translating it yet (for module-level tables). Translate it with t() where it is shown. */
export const T=(text:string):string=>text;
