import {initials} from './format';

export function Avatar({profile,name,size=40}:{profile:{photo:string|null}|null;name:string;size?:number}){
  return profile?.photo?<img className="avatar" width={size} height={size} src={profile.photo} alt=""/>:<span className="avatar avatar-initials" aria-hidden="true">{initials(name)}</span>;
}
