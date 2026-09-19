import { mount } from 'svelte'
import './app.css'
import App from './App.svelte'

// The load reveal. The class goes on <html> a frame after the document is ready, so the first
// paint already has the elements at opacity 0 rather than flashing them. Each element drops out
// of the animation on animationend, so a later re-render cannot replay its entrance.
document.documentElement.classList.add('js');
const startReveal = () => requestAnimationFrame(() => {
  document.documentElement.classList.add('is-ready');
  document.addEventListener('animationend', (e) => {
    if (e.animationName === 'reveal') e.target.classList.add('is-revealed');
  }, true);
});
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', startReveal, { once: true });
} else {
  startReveal();
}
export default mount(App, { target: document.getElementById('app') })
