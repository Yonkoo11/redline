import { mount } from 'svelte'
import './app.css'
import Policy from './Policy.svelte'
export default mount(Policy, { target: document.getElementById('app') })
