const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const state={days:30,dashboard:null,orders:[],inventory:[],customers:null,quality:null,insights:null,health:null,orderPage:1,customerPage:1};

async function api(path,opt={}){
  const res=await fetch(path,{headers:{'Content-Type':'application/json',...(opt.headers||{})},...opt});
  const data=await res.json().catch(()=>({}));
  if(!res.ok)throw new Error(data.error||`Request failed (${res.status})`);
  return data;
}
function esc(v=''){return String(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
function money(v,currency='USD'){return new Intl.NumberFormat('en-US',{style:'currency',currency,maximumFractionDigits:0}).format(Number(v||0))}
function compactMoney(v){return new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',notation:'compact',maximumFractionDigits:1}).format(Number(v||0))}
function pct(v){const n=Number(v||0);return `${n>0?'+':''}${n.toFixed(1)}%`}
function dt(v){return v?new Date(v).toLocaleString([],{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}):'—'}
function age(v){if(!v)return '—';const h=Math.floor((Date.now()-new Date(v).getTime())/36e5);if(h<1)return '<1h';if(h<24)return `${h}h`;return `${Math.floor(h/24)}d`}
function toast(msg){const el=$('#toast');el.textContent=msg;el.classList.add('show');clearTimeout(toast.t);toast.t=setTimeout(()=>el.classList.remove('show'),2600)}
function go(view){$$('.view').forEach(v=>v.classList.remove('active'));$(`#${view}View`).classList.add('active');$$('.nav-tab').forEach(b=>b.classList.toggle('active',b.dataset.view===view));window.scrollTo({top:0,behavior:'smooth'})}

function chart(svg,data,{large=false}={}){
  if(!data?.length){svg.innerHTML='';return}
  const W=large?980:760,H=large?330:260,pad={l:50,r:15,t:16,b:32};
  const vals=data.map(d=>Number(d.sales||0)),max=Math.max(...vals,1),min=0;
  const x=i=>pad.l+(i/(Math.max(data.length-1,1)))*(W-pad.l-pad.r);
  const y=v=>H-pad.b-((v-min)/(max-min||1))*(H-pad.t-pad.b);
  const points=data.map((d,i)=>`${x(i)},${y(Number(d.sales||0))}`).join(' ');
  let area=`${pad.l},${H-pad.b} ${points} ${x(data.length-1)},${H-pad.b}`;
  let grid='';
  for(let i=0;i<5;i++){const yy=pad.t+i*(H-pad.t-pad.b)/4;const val=max*(1-i/4);grid+=`<line x1="${pad.l}" y1="${yy}" x2="${W-pad.r}" y2="${yy}" stroke="#eadfd6" stroke-width="1"/><text x="${pad.l-8}" y="${yy+3}" text-anchor="end" font-size="9" fill="#9a8982">${compactMoney(val)}</text>`}
  let labels='';const step=Math.max(1,Math.floor(data.length/5));
  data.forEach((d,i)=>{if(i%step===0||i===data.length-1){labels+=`<text x="${x(i)}" y="${H-8}" text-anchor="middle" font-size="8" fill="#9a8982">${new Date(d.day+'T12:00:00').toLocaleDateString([],{month:'short',day:'numeric'})}</text>`}});
  svg.setAttribute('viewBox',`0 0 ${W} ${H}`);
  svg.innerHTML=`${grid}<polygon points="${area}" fill="rgba(185,108,100,.10)"/><polyline points="${points}" fill="none" stroke="#8f4f47" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>${data.map((d,i)=>`<circle cx="${x(i)}" cy="${y(Number(d.sales||0))}" r="${large?3.2:2.6}" fill="#fffdf9" stroke="#8f4f47" stroke-width="2"><title>${d.day}: ${money(d.sales)} · ${d.orders} orders</title></circle>`).join('')}${labels}`;
}

async function refreshCore(){
  const q=`?days=${state.days}`;
  const [d,o,i,c,qy,h]=await Promise.all([api('/api/dashboard'+q),api('/api/orders?limit=120'),api('/api/inventory'+q),api('/api/customers'),api('/api/data-quality'),api('/api/health')]);
  Object.assign(state,{dashboard:d,orders:o.orders,inventory:i.products,customers:c,quality:qy,health:h});
  renderHeader();renderPulse();renderSales();renderOrders();renderInventory();renderCustomers();renderData();
}
function renderHeader(){
  const p=$('#connectionPill');const live=state.health.shopify_mode==='live';
  p.classList.toggle('live',live);p.innerHTML=`<i></i>${live?esc(state.health.shop):'Demo store'}`;
}
function renderPulse(){
  const d=state.dashboard;
  $('#mSales').textContent=money(d.sales);$('#mOrders').textContent=d.orders;$('#mAov').textContent=money(d.aov);$('#mRepeat').textContent=`${d.repeat_customer_rate}%`;$('#mAttention').textContent=d.inventory_at_risk+d.unfulfilled_orders;
  const sg=$('#mSalesGrowth');sg.textContent=`${pct(d.sales_growth)} vs prior period`;sg.className=d.sales_growth>=0?'up':'down';
  const og=$('#mOrderGrowth');og.textContent=`${pct(d.order_growth)} vs prior period`;og.className=d.order_growth>=0?'up':'down';
  chart($('#salesChart'),d.daily_sales);chart($('#salesChartLarge'),d.daily_sales,{large:true});
  $('#chartCaption').innerHTML=`<span>${d.daily_sales.length} reporting days</span><span>${d.unique_customers} unique customers · ${d.orders} orders</span>`;
  $('#alertCount').textContent=d.alerts.length;
  $('#alertList').innerHTML=d.alerts.slice(0,5).map(a=>`<div class="alert-row ${a.severity}"><span class="alert-dot"></span><div><b>${esc(a.title)}</b><p>${esc(a.detail)}</p></div></div>`).join('')||'<div class="empty-state">No active alerts.</div>';
  const max=Math.max(...d.top_products.map(x=>Number(x.revenue||0)),1);
  $('#topProducts').innerHTML=d.top_products.map((p,idx)=>`<div class="product-line"><span class="rank-badge">${idx+1}</span><div><b>${esc(p.title)}</b><small>${esc(p.sku||'SKU missing')} · ${p.units} units</small></div><div class="bar-mini"><i style="width:${Number(p.revenue||0)/max*100}%"></i></div><span class="money-small">${money(p.revenue)}</span></div>`).join('');
  const total=Math.max(d.channels.reduce((s,x)=>s+Number(x.sales||0),0),1);
  $('#channelMix').innerHTML=d.channels.map(x=>`<div class="channel-row"><div><b>${esc(x.channel)}</b><small>${x.orders} orders</small></div><b>${Math.round(Number(x.sales)/total*100)}%</b><div class="channel-track"><i style="width:${Number(x.sales)/total*100}%"></i></div></div>`).join('');
}
function renderSales(){
  const d=state.dashboard;$('#salesPeriodTitle').textContent=`Last ${state.days} days`;
  chart($('#salesChartLarge'),d.daily_sales,{large:true});
  $('#salesProductRanking').innerHTML=d.top_products.map((p,i)=>`<div class="rank-item"><span class="ordinal">0${i+1}</span><div><b>${esc(p.title)}</b><small>${p.units} units · ${esc(p.sku||'SKU missing')}</small></div><strong>${money(p.revenue)}</strong></div>`).join('');
  const total=Math.max(d.channels.reduce((s,x)=>s+Number(x.sales||0),0),1);
  $('#salesChannelTable').innerHTML=`<table class="data-table"><thead><tr><th>Channel</th><th>Orders</th><th>Sales</th><th>Share</th></tr></thead><tbody>${d.channels.map(x=>`<tr><td><div class="cell-main"><b>${esc(x.channel)}</b></div></td><td>${x.orders}</td><td>${money(x.sales)}</td><td>${(Number(x.sales)/total*100).toFixed(1)}%</td></tr>`).join('')}</tbody></table>`;
}
function renderOrders(){
  $('#orderUnfulfilled').textContent=state.dashboard.unfulfilled_orders;
  const q=($('#orderSearch')?.value||'').toLowerCase(),filter=$('#orderFilter')?.value||'';
  const rows=state.orders.filter(o=>(!filter||o.fulfillment_status===filter)&&(!q||[o.order_name,o.customer_name,o.customer_email].join(' ').toLowerCase().includes(q)));
  const per=15,pages=Math.max(1,Math.ceil(rows.length/per));state.orderPage=Math.min(state.orderPage,pages);const shown=rows.slice((state.orderPage-1)*per,state.orderPage*per);
  $('#ordersTable').innerHTML=`<table class="data-table"><thead><tr><th>Order</th><th>Customer</th><th>Placed</th><th>Value</th><th>Payment</th><th>Fulfillment</th><th>Channel</th></tr></thead><tbody>${shown.map(o=>`<tr data-order="${o.id}"><td><div class="cell-main"><b>${esc(o.order_name)}</b><small>${o.item_count||0} items</small></div></td><td><div class="cell-main"><b>${esc(o.customer_name||'Guest')}</b><small>${esc(o.customer_email||'')}</small></div></td><td>${dt(o.created_at)}<br><span class="cell-main"><small>${age(o.created_at)} old</small></span></td><td>${money(o.total,o.currency)}</td><td>${esc(o.financial_status)}</td><td><span class="status-pill ${esc(o.fulfillment_status)}">${esc(o.fulfillment_status.replaceAll('_',' '))}</span></td><td>${esc(o.channel)}</td></tr>`).join('')}</tbody></table>`;
  $('#ordersPager').innerHTML=`<span>${rows.length} orders · page ${state.orderPage} of ${pages}</span><div><button data-order-page="prev" ${state.orderPage<=1?'disabled':''}>← Previous</button><button data-order-page="next" ${state.orderPage>=pages?'disabled':''}>Next →</button></div>`;
}
function renderInventory(){
  const p=state.inventory;const counts={HEALTHY:0,WATCH:0,LOW:0,CRITICAL:0,UNKNOWN:0};p.forEach(x=>counts[x.risk]=(counts[x.risk]||0)+1);
  $('#inventorySummary').innerHTML=Object.entries(counts).map(([k,v])=>`<article><span>${k.replace('_',' ')}</span><b>${v}</b></article>`).join('');
  $('#inventoryTable').innerHTML=`<table class="data-table"><thead><tr><th>Product</th><th>SKU</th><th>On hand</th><th>30d units</th><th>Daily velocity</th><th>Days cover</th><th>Reorder point</th><th>Status</th></tr></thead><tbody>${p.map(x=>`<tr><td><div class="cell-main"><b>${esc(x.title)}</b><small>${esc(x.product_type||'')}</small></div></td><td>${esc(x.sku||'—')}</td><td>${x.inventory??'—'}</td><td>${x.units_30}</td><td>${x.daily_velocity}</td><td>${x.days_cover??'—'}</td><td>${x.reorder_point}</td><td><span class="risk-pill ${x.risk}">${x.risk}</span></td></tr>`).join('')}</tbody></table>`;
}
function renderCustomers(){
  const counts=state.customers.counts||{};const keys=['VIP','LOYAL','REPEAT','NEW','AT_RISK','DORMANT'];
  $('#segmentCards').innerHTML=keys.map(k=>`<article class="segment-card"><span>${k.replace('_',' ')}</span><b>${counts[k]||0}</b></article>`).join('');
  const q=($('#customerSearch')?.value||'').toLowerCase(),filter=$('#segmentFilter')?.value||'';
  const rows=state.customers.customers.filter(c=>(!filter||c.segment===filter)&&(!q||[c.name,c.email,c.country].join(' ').toLowerCase().includes(q)));
  const per=15,pages=Math.max(1,Math.ceil(rows.length/per));state.customerPage=Math.min(state.customerPage,pages);const shown=rows.slice((state.customerPage-1)*per,state.customerPage*per);
  $('#customersTable').innerHTML=`<table class="data-table"><thead><tr><th>Customer</th><th>Country</th><th>Orders</th><th>Lifetime spend</th><th>Last order</th><th>Segment</th></tr></thead><tbody>${shown.map(c=>`<tr><td><div class="cell-main"><b>${esc(c.name)}</b><small>${esc(c.email||'')}</small></div></td><td>${esc(c.country||'—')}</td><td>${c.orders}</td><td>${money(c.spend)}</td><td>${c.recency_days===999?'—':`${c.recency_days} days ago`}</td><td><span class="segment-pill ${c.segment}">${c.segment.replace('_',' ')}</span></td></tr>`).join('')}</tbody></table>`;
  $('#customersPager').innerHTML=`<span>${rows.length} customers · page ${state.customerPage} of ${pages}</span><div><button data-customer-page="prev" ${state.customerPage<=1?'disabled':''}>← Previous</button><button data-customer-page="next" ${state.customerPage>=pages?'disabled':''}>Next →</button></div>`;
}
function renderData(){
  const q=state.quality;$('#qualityScore').textContent=`${q.score}%`;
  $('#qualityIssues').innerHTML=[['Products',q.products],['Missing SKU',q.missing_sku],['Missing inventory',q.missing_inventory],['Duplicate SKU',q.duplicate_sku],['Customer email gaps',q.missing_customer_email],['Customers',q.customers]].map(([k,v])=>`<div class="quality-item"><span>${k}</span><b>${v}</b></div>`).join('');
  const live=state.health.shopify_mode==='live';$('#connectorTitle').textContent=live?`Connected · ${state.health.shop}`:'Demo snapshot';$('#connectorCopy').textContent=live?'Live Shopify credentials are configured. Run a bounded GraphQL snapshot sync, then use bulk operations/webhooks for production-scale history.':'Use the built-in commerce dataset now, or add Shopify Admin API credentials in .env for an optional live snapshot.';
  $('#syncHistory').innerHTML=`<table class="data-table"><thead><tr><th>Run</th><th>Mode</th><th>Status</th><th>Records</th><th>Note</th><th>Time</th></tr></thead><tbody>${(q.sync_runs||[]).map(r=>`<tr><td>#${r.id}</td><td>${esc(r.mode)}</td><td>${esc(r.status)}</td><td>${r.records}</td><td>${esc(r.note)}</td><td>${dt(r.created_at)}</td></tr>`).join('')}</tbody></table>`;
}
async function renderInsights(force=false){
  if(state.insights&&!force){drawInsights();return}
  $('#insightList').innerHTML='<div class="empty-state">Preparing evidence-first business brief…</div>';
  state.insights=await api(`/api/insights?days=${state.days}`);drawInsights();
}
function drawInsights(){
  const r=state.insights||{};let items=r.items||[];
  if(!items.length&&r.text){items=r.text.split(/\n+/).filter(Boolean).slice(0,6).map((t,i)=>({title:`AI observation ${i+1}`,detail:t,evidence:[]}))}
  $('#insightList').innerHTML=items.map((x,i)=>`<article class="insight-card"><span class="insight-index">${String(i+1).padStart(2,'0')}</span><div><h3>${esc(x.title||'Insight')}</h3><p>${esc(x.detail||'')}</p><div class="evidence-chips">${(x.evidence||[]).map(e=>`<span>${esc(e)}</span>`).join('')}</div></div></article>`).join('')||'<div class="empty-state">No insights available.</div>';
  const m=r.metrics||{};const pairs=[['Sales',money(m.sales)],['Orders',m.orders],['AOV',money(m.aov)],['Sales growth',pct(m.sales_growth_percent)],['Repeat rate',`${m.repeat_customer_rate_percent||0}%`],['Unfulfilled',m.unfulfilled_orders],['Inventory at risk',m.inventory_at_risk],['Data quality',`${m.data_quality?.score||0}%`],['Advisor mode',r.mode||'rules']];
  $('#evidencePack').innerHTML=pairs.map(([a,b])=>`<div class="evidence-row"><span>${esc(a)}</span><b>${esc(b)}</b></div>`).join('');
}
async function openOrder(id){
  const o=await api(`/api/orders/${id}`);const d=$('#orderDialog');
  $('#orderDetail').innerHTML=`<div class="order-detail"><div class="dialog-head"><div><span class="overline">ORDER DETAIL</span><h2>${esc(o.order_name)}</h2><p>${esc(o.customer_name||'Guest')} · ${esc(o.customer_email||'')}</p></div><button class="close-btn" onclick="document.getElementById('orderDialog').close()">×</button></div><div class="detail-grid"><div class="detail-stat"><span>Total</span><b>${money(o.total,o.currency)}</b></div><div class="detail-stat"><span>Payment</span><b>${esc(o.financial_status)}</b></div><div class="detail-stat"><span>Fulfillment</span><b>${esc(o.fulfillment_status.replaceAll('_',' '))}</b></div><div class="detail-stat"><span>Channel</span><b>${esc(o.channel)}</b></div><div class="detail-stat"><span>Placed</span><b>${dt(o.created_at)}</b></div><div class="detail-stat"><span>Country</span><b>${esc(o.customer_country||'—')}</b></div></div><div class="item-list">${(o.items||[]).map(i=>`<div class="item-row"><div><b>${esc(i.title)}</b><br><span>${esc(i.sku||'SKU missing')}</span></div><span>× ${i.quantity}</span><strong>${money(Number(i.unit_price)*Number(i.quantity),o.currency)}</strong></div>`).join('')}</div></div>`;d.showModal();
}

$$('[data-view]').forEach(b=>b.addEventListener('click',e=>{e.preventDefault();go(b.dataset.view);if(b.dataset.view==='ai')renderInsights().catch(err=>toast(err.message))}));
$$('[data-go]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.go)));
$$('[data-days]').forEach(b=>b.addEventListener('click',async()=>{state.days=Number(b.dataset.days);$$('[data-days]').forEach(x=>x.classList.toggle('active',x===b));state.insights=null;await refreshCore();toast(`Reporting window: ${state.days} days`)}));
$('#orderSearch').addEventListener('input',()=>{state.orderPage=1;renderOrders()});$('#orderFilter').addEventListener('change',()=>{state.orderPage=1;renderOrders()});$('#customerSearch').addEventListener('input',()=>{state.customerPage=1;renderCustomers()});$('#segmentFilter').addEventListener('change',()=>{state.customerPage=1;renderCustomers()});
document.addEventListener('click',e=>{const row=e.target.closest('[data-order]');if(row)return openOrder(Number(row.dataset.order)).catch(err=>toast(err.message));const op=e.target.closest('[data-order-page]');if(op){state.orderPage+=op.dataset.orderPage==='next'?1:-1;renderOrders();return}const cp=e.target.closest('[data-customer-page]');if(cp){state.customerPage+=cp.dataset.customerPage==='next'?1:-1;renderCustomers();return}});
$('#refreshInsights').addEventListener('click',()=>renderInsights(true).catch(err=>toast(err.message)));
$('#testConnection').addEventListener('click',async()=>{try{const r=await api('/api/shopify/test',{method:'POST',body:'{}'});toast(r.ok?`Connected to ${r.shop?.name||'Shopify'}`:r.message)}catch(err){toast(err.message)}});
async function liveSync(){try{const r=await api('/api/shopify/sync',{method:'POST',body:'{}'});toast(r.message);state.insights=null;await refreshCore()}catch(err){toast(err.message)}}
$('#liveSyncBtn').addEventListener('click',liveSync);$('#syncBtn').addEventListener('click',liveSync);

refreshCore().catch(err=>toast(err.message));
