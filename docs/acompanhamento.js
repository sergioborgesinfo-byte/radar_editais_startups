(function(){
'use strict';
var panel=document.getElementById('busca-panel'), button=document.getElementById('busca-toggle');
var snapshot=null, page=1, perPage=20, busy=false;
var base='https://raw.githubusercontent.com/sergioborgesinfo-byte/radar_editais_startups/main/data/';
function el(id){return document.getElementById(id)}
function escape(s){return String(s||'').replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function label(status){return {'confirmada_no_conteudo':'Relevância confirmada','nao_confirmada_no_texto':'Não confirmada no texto','falha_leitura':'Leitura pendente','pendente_leitura':'Leitura pendente','pendente_ia':'Análise pendente','pendente_evidencia':'Evidências pendentes'}[status]||'Ainda não examinada'}
function motivo(x){if(!/^(falha_leitura|pendente_leitura|pendente_ia|pendente_evidencia)$/.test(x.status||''))return '';var m=x.motivo||'';if(m.indexOf('429')>=0)return 'Limite do serviço de IA atingido';if(m.indexOf('robots')>=0)return 'Site não autoriza leitura automática';if(m.indexOf('dinamica')>=0)return 'Página precisa de outro método de leitura';if(m.indexOf('pagina_http')===0)return 'Página recusou o acesso';if(m.indexOf('gemini')===0)return 'Serviço de IA indisponível';return m?'Leitura ou evidência precisa de nova tentativa':''}
function render(){
 if(!snapshot)return;
 var checked={};snapshot.confirmacoes.forEach(function(x){checked[x.url]=x});
 var vigencia={}, fase=snapshot.vigencia||{};(fase.resultados||[]).forEach(function(x){vigencia[x.url]=x});
 var confirms=snapshot.confirmacoes.filter(function(x){return x.status==='confirmada_no_conteudo'}).length;
 var pending=snapshot.confirmacoes.filter(function(x){return /falha|pendente/.test(x.status)}).length;
 var vigPending=(fase.pendentes||[]).length;
 el('busca-stats').innerHTML=[['Links descobertos',snapshot.links],['Candidatos na triagem',snapshot.candidatos],['Relevância confirmada',confirms],['Vigência examinada',fase.examinadas||0],['Abertas publicadas',fase.abertas_publicadas||0],['Pendências de vigência',vigPending]].map(function(x){return '<div class="busca-stat"><strong>'+x[1]+'</strong><span>'+x[0]+'</span></div>'}).join('');
 el('busca-date').textContent='Último resultado salvo: '+new Date(snapshot.atualizado_em).toLocaleString('pt-BR')+'.';
 var q=el('busca-q').value.toLowerCase(), filter=el('busca-filter').value;
 var items=snapshot.itens.map(function(x){return Object.assign({},x,checked[x.url]||{},{vigencia:vigencia[x.url]||null})}).filter(function(x){
 return (!q||((x.dados&&x.dados.titulo)||x.titulo||'').toLowerCase().indexOf(q)>=0||x.url.toLowerCase().indexOf(q)>=0)&&(!filter||(filter==='confirmada'?x.status==='confirmada_no_conteudo':filter==='pendente'?/falha|pendente/.test(x.status||''):!x.status));
 });
 items.sort(function(a,b){return Number(b.status==='confirmada_no_conteudo')-Number(a.status==='confirmada_no_conteudo')});
 var pages=Math.max(1,Math.ceil(items.length/perPage));page=Math.min(page,pages);
 el('busca-counter').textContent=items.length+' páginas nesta seleção · página '+page+' de '+pages;
 el('busca-list').innerHTML=items.slice((page-1)*perPage,page*perPage).map(function(x){
 var d=x.dados||{}, title=d.titulo||x.titulo||'Página descoberta';
 var url=/^https?:\/\//.test(x.url)?x.url:'';
 var vl=x.vigencia?(x.vigencia.status==='aberta_confirmada'?'Aberta e confirmada':x.vigencia.status==='encerrada'?'Encerrada':'Vigência pendente'):'Vigência não verificada';
 return '<article class="item"><h2>'+escape(title)+'</h2><div class="tags"><span class="tag">'+escape(label(x.status))+'</span><span class="tag new">'+escape(vl)+'</span></div>'+(d.resumo?'<p class="desc">'+escape(d.resumo)+'</p>':'')+(motivo(x)?'<p class="org">'+escape(motivo(x))+'</p>':'')+(url?'<a class="lnk" href="'+escape(url)+'" target="_blank" rel="noopener noreferrer">Abrir fonte</a>':'')+'</article>';
 }).join('')||'<p class="empty">Nenhuma página neste filtro.</p>';
 el('busca-prev').disabled=page<=1;el('busca-next').disabled=page>=pages;
}
async function json(url){var controller=new AbortController(),timer=setTimeout(function(){controller.abort()},12000);try{var r=await fetch(url,{cache:'no-store',signal:controller.signal});if(!r.ok)throw Error('Dados indisponíveis');return await r.json()}finally{clearTimeout(timer)}}
async function refresh(){
 if(busy)return;busy=true;el('busca-refresh').disabled=true;
 try{
  if(!snapshot){snapshot=await json('busca.json');render()}
  var values=await Promise.allSettled([json(base+'triagem-descobertas.json'),json(base+'oportunidades-conteudo.json'),json('https://api.github.com/repos/sergioborgesinfo-byte/radar_editais_startups/actions/workflows/conteudo.yml/runs?per_page=1')]);
  if(values[0].status==='fulfilled'){var t=values[0].value;snapshot.itens=t.itens;snapshot.links=t.links_recebidos;snapshot.candidatos=t.contagem.prioridade_verificacao||0}
  if(values[1].status==='fulfilled'){snapshot.confirmacoes=values[1].value.itens;snapshot.atualizado_em=values[1].value.atualizado_em}
  if(values[2].status==='fulfilled'){var run=values[2].value.workflow_runs[0];el('busca-status').textContent=run.status==='completed'?(run.conclusion==='success'?'Último lote concluído.':'Último lote terminou com pendências; veja os resultados salvos.'):'Análise em andamento no GitHub. Os números abaixo são do último resultado salvo.'}
  else el('busca-status').textContent='Resultados salvos disponíveis. Não foi possível consultar o status da execução agora.';
  render();
 }catch(e){el('busca-status').textContent='Não foi possível carregar o acompanhamento. Toque em Atualizar para tentar novamente.'}
 finally{busy=false;el('busca-refresh').disabled=false}
}
button.onclick=function(){panel.hidden=!panel.hidden;button.setAttribute('aria-expanded',String(!panel.hidden));if(!panel.hidden){refresh();panel.scrollIntoView({block:'start',behavior:'smooth'})}};
el('busca-refresh').onclick=refresh;
['busca-q','busca-filter'].forEach(function(id){el(id).oninput=function(){page=1;render()}});
el('busca-prev').onclick=function(){page--;render()};el('busca-next').onclick=function(){page++;render();el('busca-counter').scrollIntoView({block:'start'})};
setInterval(function(){if(!panel.hidden&&!document.hidden)refresh()},60000);
document.addEventListener('visibilitychange',function(){if(!document.hidden&&!panel.hidden)refresh()});
})();
