"""Original, browser-local section search; no indexing service or remote calls."""

SEARCH_PANEL = """<section id="section-search" class="card search-panel" hidden aria-labelledby="search-heading">
<h2 id="search-heading">Find on this page</h2>
<label for="section-query">Search sections</label>
<input id="section-query" type="search" maxlength="160" autocomplete="off" aria-controls="page-sections">
<button id="section-reset" type="button">Clear search</button>
<p id="section-search-status" role="status" aria-live="polite"></p>
</section>"""

SEARCH_CSS = """
.search-panel { margin-bottom: 1rem; }
.search-panel label { display: block; font-weight: 600; }
.search-panel input, .search-panel button { margin-block: .5rem; }
#page-sections > [hidden], #section-search[hidden] { display: none !important; }
"""

SEARCH_JS = r"""'use strict';
(() => {
  const panel=document.getElementById('section-search');
  const query=document.getElementById('section-query');
  const reset=document.getElementById('section-reset');
  const status=document.getElementById('section-search-status');
  const sections=Array.from(document.getElementById('page-sections').children);
  const normalize=s=>s.normalize('NFKC').toLowerCase().replace(/\s+/g,' ').trim();
  const index=sections.map(section=>normalize(section.textContent));
  function update(){
    const term=normalize(query.value);
    let count=0;
    sections.forEach((section,i)=>{
      const match=index[i].includes(term);
      section.hidden=!match;
      if(match)count++;
    });
    status.textContent=count+' of '+sections.length+' sections shown.';
  }
  query.addEventListener('input',update);
  reset.addEventListener('click',()=>{query.value='';update();query.focus();});
  panel.hidden=false;
  update();
})();
"""
