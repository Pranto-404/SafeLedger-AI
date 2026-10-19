import {t} from './i18n';
export function PasswordStrength({password,username}:{password:string;username:string}) {
  const unique=new Set(password.toLowerCase()).size;
  const common=/^(password|12345678|qwerty|abcdefgh|11111111|letmein|welcome)/i.test(password)|| (!!username&&password.toLowerCase()===username.toLowerCase());
  const variety=[/[a-z]/,/[A-Z]/,/\d/,/[^a-zA-Z0-9]/].filter(r=>r.test(password)).length;
  const score=password.length<8?0:common||unique<4?1:password.length>=16&&unique>=8?4:password.length>=12&&variety>=3?4:password.length>=10&&variety>=2?3:2;
  const labels=[t('Too short'),t('Weak'),t('Fair'),t('Good'),t('Strong')];
  return <div className="password-strength"><meter aria-label={t('Estimated password strength')} min={0} max={4} value={score}/><small>{password?`${labels[score]} · `:''}{password.length<8?'Use at least 8 characters.':t('Longer, unique passwords are safer. Strength is an estimate.')}</small></div>;
}
