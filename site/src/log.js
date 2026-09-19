import { mount } from 'svelte'
import './app.css'
import Page from './Log.svelte'
export default mount(Page, { target: document.getElementById('app') })
