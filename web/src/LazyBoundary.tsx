import {Component,type ReactNode} from 'react';
export class LazyBoundary extends Component<{children:ReactNode},{failed:boolean}>{
 state={failed:false};
 static getDerivedStateFromError(){return {failed:true};}
 render(){return this.state.failed?<section className="panel" role="alert"><h2>This panel could not load.</h2><p>Your saved records are still on the server. Reload to open the latest version.</p><button onClick={()=>window.location.reload()}>Reload workspace</button></section>:this.props.children;}
}
