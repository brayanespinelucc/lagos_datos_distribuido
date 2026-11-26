"use strict";
(() => {
  const data = window.LAGO;
  const main = document.querySelector("#contenido");
  if (!data) {
    main.textContent = "Faltan los datos del portal. Descomprima el paquete completo y abra index.html.";
    return;
  }
  const pages = {lago:"Explorador del lago",flujo:"Flujo de datos",consultas:"Consultas SQL",gobierno:"Gobierno de datos",monitoreo:"Monitoreo",laboratorio:"Laboratorio",sustentacion:"Sustentación",resumen:"Resumen", infraestructura:"Infraestructura", trazabilidad:"Trazabilidad", evidencias:"Evidencias", documentos:"Documentos"};
  const moments = {1:"Infraestructura base", 2:"Lago y gobierno de datos", 3:"Monitoreo y operación"};
  const weights = {1:30, 2:35, 3:35};
  const roles = {"minio-lb":"Balanceador MinIO", "rke2-lb":"Balanceador RKE2", minio:"Nodo MinIO", "rke2-server":"Control plane", "rke2-worker":"Worker RKE2"};
  const shapes = {
    layers:'<path d="m2 7 10-5 10 5-10 5zM2 12l10 5 10-5M2 17l10 5 10-5"/>',
    flow:'<circle cx="5" cy="5" r="2"/><circle cx="19" cy="12" r="2"/><circle cx="5" cy="19" r="2"/><path d="M7 5h4v14H7m4-7h6"/>',
    code:'<path d="m7 7-5 5 5 5m10-10 5 5-5 5m-3-14-4 18"/>',
    pulse:'<path d="M2 12h4l3-8 5 16 3-8h5"/>',
    experiment:'<path d="M8 3h8m-6 0v6L4 19a1 1 0 0 0 1 2h14a1 1 0 0 0 1-2L14 9V3M7 16h10"/>',
    play:'<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m10 8 5 4-5 4z"/>',
    overview:'<rect x="3" y="3" width="7" height="7" rx="1.4"/><rect x="14" y="3" width="7" height="7" rx="1.4"/><rect x="3" y="14" width="7" height="7" rx="1.4"/><rect x="14" y="14" width="7" height="7" rx="1.4"/>',
    network:'<rect x="8.5" y="2.5" width="7" height="5" rx="1"/><rect x="2.5" y="16" width="7" height="5" rx="1"/><rect x="14.5" y="16" width="7" height="5" rx="1"/><path d="M12 7.5v4.5m-6 4v-4h12v4"/>',
    rows:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M3 14h18m-12-5v11"/>',
    evidence:'<path d="M8 4H5v15h14v-5M8 4V2h8l4 4v3M8 4v12h5"/><path d="m14 11 2 2 5-5"/>',
    folder:'<path d="M3 7V5a1.5 1.5 0 0 1 1.5-1.5H10l2 2H19a2 2 0 0 1 2 2v2"/><path d="M3 8.5h18l-2.3 11H5z"/>',
    book:'<path d="M3 4.5c3.3-1 6.1-.6 9 1.2 2.9-1.8 5.7-2.2 9-1.2v14c-3.2-.9-6.1-.6-9 1.2-2.9-1.8-5.8-2.1-9-1.2zM12 6v13"/>',
    git:'<circle cx="6.5" cy="5" r="2"/><circle cx="6.5" cy="19" r="2"/><circle cx="17" cy="6.5" r="2"/><path d="M6.5 7v10m0-3c7 0 10.5-1 10.5-5.5"/>',
    external:'<path d="M13 4h7v7m0-7L10 14"/><path d="M10 5H5v14h14v-5"/>',
    arrow:'<path d="M4 12h15m-6-6 6 6-6 6"/>', chevron:'<path d="m9 5 7 7-7 7"/>',
    close:'<path d="m5 5 14 14m0-14L5 19"/>',menu:'<path d="M3 5h18M3 12h18M3 19h18"/>',
    server:'<rect x="3" y="3" width="18" height="7" rx="1.5"/><rect x="3" y="14" width="18" height="7" rx="1.5"/><path d="M7 6.5h1m-1 11h1m5-11h4m-4 11h4"/>',
    doc:'<path d="M5 2.5h9l5 5v14H5zM14 3v5h5M8 12h8m-8 4h7"/>',
    photo:'<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8" cy="8" r="1.4"/><path d="m3 17 5-5 4 4 3-3 6 6"/>',
    download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v4h16v-4"/>',
    search:'<circle cx="10.3" cy="10.3" r="6.8"/><path d="m15.5 15.5 5 5"/>',
    eye:'<path d="M2 12c3-5 6-7 10-7s7 2 10 7c-3 5-6 7-10 7S5 17 2 12z"/><circle cx="12" cy="12" r="2.8"/>',
    box:'<path d="m3 6 9-4 9 4-9 4zM3 6v12l9 4 9-4V6m-9 4v12"/>'
  };
  const icon = name => '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true">' + (shapes[name] || shapes.doc) + '</svg>';
  const escape = value => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[ch]);
  const norm = value => String(value ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLocaleLowerCase("es");
  const fmt = value => Number(value).toLocaleString("es-CO",{maximumFractionDigits:1});
  const sizeName = size => size < 1024 ? fmt(size)+" B" : size < 1048576 ? fmt(size/1024)+" KiB" : fmt(size/1048576)+" MiB";
  const fileUrl = file => file.url.split("/").map(encodeURIComponent).join("/");
  const fileMap = new Map(data.files.map(file => [file.path,file]));
  const bySuffix = suffix => data.files.find(file => file.path.endsWith(suffix));
  const vms = data.inventory.vms;
  const reqs = data.requirements;
  const verified = row => norm(row.estado) === "implementado y verificado";
  const viewer = document.querySelector("#viewer");
  let section = "resumen";
  let params = new URLSearchParams();
  let lastViewButton;
  for (const target of document.querySelectorAll("[data-i]")) target.innerHTML = icon(target.dataset.i);
  function routeLink(sectionName, parameters={}) {
    const search = new URLSearchParams(Object.entries(parameters).filter(([,value]) => value !== ""));
    return "#" + sectionName + (search.size ? "?"+search : "");
  }
  function pageHead(label,title,body) {
    return '<header class="page-head"><p class="eyebrow">'+escape(label)+'</p><h1>'+escape(title)+'</h1><p>'+escape(body)+'</p></header>';
  }
  function linkButton(label,href,kind="button") {
    return '<a class="'+kind+'" href="'+escape(href)+'">'+escape(label)+icon("arrow")+'</a>';
  }
  function buttonView(file,style,label) {
    return '<button class="'+style+'" type="button" data-view="'+escape(file.path)+'" aria-label="Vista previa de '+escape(file.title)+'">'+(label || icon("eye")+'<span class="view-label">Ver</span>')+'</button>';
  }
  function download(file) {
    return '<a class="icon-button" href="'+escape(fileUrl(file))+'" download aria-label="Descargar '+escape(file.title)+' ('+escape(file.format)+')">'+icon("download")+'</a>';
  }
  function findAssociations(file) {
    return reqs.filter(row => {
      const declared = (row.evidencia_asociada || "").split(/[;,|\n]+/).map(path => path.trim().replace(/^[\s\`(]+|[\s\`.)]+$/g,""));
      return declared.some(path => path === file.path || (path.includes("/") && file.path.startsWith(path.replace(/\/$/,"")+"/")));
    }).map(row => row.id);
  }
  for (const file of data.files) file.references = file.kind==="Evidencia" ? findAssociations(file) : [];
  function momentStatus(number) {
    const subset = reqs.filter(row => row.momento===String(number));
    const done = subset.filter(verified).length;
    if (!subset.length) return "Sin clasificar";
    if (done === subset.length) return "Verificado";
    const underway = subset.some(row => !["pendiente","bloqueado"].includes(norm(row.estado)));
    return underway ? "En desarrollo" : "Pendiente";
  }
  function diagram() {
    const counts = [vms.filter(vm=>vm.role==="minio").length,vms.filter(vm=>["rke2-server","rke2-worker"].includes(vm.role)).length];
    return '<figure class="hero-figure"><svg class="diagram-thumb" viewBox="0 0 280 155" aria-label="Proxmox VE conecta dos balanceadores. El primero sirve '+counts[0]+' nodos MinIO y el segundo '+counts[1]+' nodos RKE2." role="img">'+
      '<g fill="none" stroke="#9bd6d0" stroke-width="1.4"><path d="M140 39v13H71v15m69-15h69v15M71 92v18m138-18v18"/></g>'+
      '<g fill="#204b5f" stroke="#76a7b0"><rect x="86" y="6" width="108" height="33" rx="6"/><rect x="17" y="67" width="109" height="26" rx="5"/><rect x="155" y="67" width="108" height="26" rx="5"/></g>'+
      '<g fill="#193e51" stroke="#80bfb9"><rect x="17" y="110" width="109" height="33" rx="6"/><rect x="155" y="110" width="108" height="33" rx="6"/></g>'+
      '<g text-anchor="middle" font-family="DM Sans, Arial, sans-serif" fill="#edf9f8" font-size="12" font-weight="650"><text x="140" y="27">Proxmox VE</text><text x="71" y="84" font-size="11">lb-minio</text><text x="209" y="84" font-size="11">lb-k8s</text><text x="71" y="131">MinIO × '+counts[0]+'</text><text x="209" y="131">RKE2 × '+counts[1]+'</text></g></svg><figcaption>Topología prevista en el inventario</figcaption></figure>';
  }
  function metric(value,label,shape) {
    return '<div class="metric"><div><strong>'+fmt(value)+'</strong><span>'+escape(label)+'</span></div><span class="metric-icon">'+icon(shape)+'</span></div>';
  }
  function quickRow(file) {
    const previewable = file.preview || ["PNG","SVG","JPG","PDF"].includes(file.format);
    const contents = '<span class="file-mark">'+icon(file.kind==="Diagrama"?"network":"doc")+'</span><span><strong>'+escape(file.title)+'</strong><small>'+escape(file.format)+' · '+sizeName(file.size)+'</small></span>'+icon("chevron");
    return previewable
      ? '<button class="qdoc" type="button" data-view="'+escape(file.path)+'">'+contents+'</button>'
      : '<a class="qdoc" href="'+escape(fileUrl(file))+'" download>'+contents+'</a>';
  }
  function home() {
    const quick = [bySuffix("/entrega/informe-final.pdf") || bySuffix("/entrega/informe.pdf"),fileMap.get("REQUIREMENTS_MATRIX.csv"),bySuffix("architecture/diagrams/arquitectura.svg"),fileMap.get("EVIDENCE_INDEX.md")].filter(Boolean).slice(0,3);
    const stages = Object.entries(moments).map(([num,name]) =>
      '<a class="stage" href="'+escape(routeLink("trazabilidad",{momento:num}))+'"><span class="stage-mark">M'+num+'</span><span><strong>'+escape(name)+'</strong><small>'+weights[num]+' % de la evaluación · '+momentStatus(num)+'</small></span>'+icon("chevron")+'</a>'
    ).join("");
    return '<section class="hero"><div><p class="eyebrow">Portal de Demostración del Proyecto</p><h1>Lago de Datos Distribuido</h1><p>Diseño e implementación de una plataforma empresarial de datos. Consulte la arquitectura y los resultados registrados en el laboratorio remoto.</p>'+linkButton("Explorar infraestructura","#infraestructura")+'</div>'+diagram()+'</section>'+
      '<section class="metrics" aria-label="Indicadores de este corte">'+metric(vms.length,"Máquinas virtuales previstas","server")+metric(reqs.length,"Requisitos trazados","rows")+metric(reqs.filter(verified).length,"Requisitos verificados","evidence")+'</section>'+
      '<div class="two-col"><section class="panel"><div class="panel-head"><h2>Momentos de evaluación</h2></div><div class="panel-body stages">'+stages+'</div><div class="panel-foot">'+linkButton("Consultar la matriz completa","#trazabilidad","plain-button")+'</div></section>'+
      '<section class="panel"><div class="panel-head"><h2>Documentos de consulta</h2></div><div class="panel-body quickdocs">'+quick.map(quickRow).join("")+'</div><div class="panel-foot">'+linkButton("Abrir centro documental","#documentos","plain-button")+'</div></section></div>';
  }
  function searchField(label,placeholder) {
    return '<label class="field grow"><span>'+escape(label)+'</span><span class="input-wrap">'+icon("search")+'<input type="search" name="q" placeholder="'+escape(placeholder)+'" value="'+escape(params.get("q") || "")+'"></span></label>';
  }
  function selectField(label,key,options) {
    return '<label class="field"><span>'+escape(label)+'</span><select name="'+key+'"><option value="">Todos</option>'+options.map(([value,title]) =>
      '<option value="'+escape(value)+'"'+(params.get(key)===value ? " selected":"")+'>'+escape(title)+'</option>'
    ).join("")+'</select></label>';
  }
  function countLine(noun,num) {
    return '<p class="matches" role="status">'+escape(noun)+' <strong>'+fmt(num)+'</strong></p>';
  }
  function empty() {
    return '<p class="empty">Ningún resultado coincide con los filtros.</p>';
  }
  function inventoryRows() {
    const query = norm(params.get("q"));
    const filtered = vms.filter(vm => norm([vm.hostname,vm.ip,vm.id,vm.role,roles[vm.role]].join(" ")).includes(query));
    return countLine("Máquinas coincidentes ·",filtered.length) + (!filtered.length ? empty() :
      '<div class="list-rows table-wrap" tabindex="0" aria-label="Inventario de VM"><table><thead><tr><th>Hostname</th><th>Función</th><th>IP propuesta</th><th>vCPU</th><th>RAM (GiB)</th><th>Discos (GiB)</th></tr></thead><tbody>'+filtered.map(vm => {
        const disks = vm.data_disks.map(d=>d.size_gib);
        return '<tr><td class="mono">'+escape(vm.hostname)+'</td><td>'+escape(roles[vm.role] || vm.role)+'</td><td class="mono">'+escape(vm.ip)+'</td><td>'+fmt(vm.vcpus)+'</td><td>'+fmt(vm.memory_mib/1024)+'</td><td>'+fmt(vm.os_disk_gib)+(disks.length ? ' + '+disks.map(fmt).join(' + '):'')+'</td></tr>';
      }).join("")+'</tbody></table></div>');
  }
  function infra() {
    const net = data.inventory.network;
    const figures = ["architecture/diagrams/arquitectura.svg","architecture/diagrams/red.svg"].map(path=>fileMap.get(path)).filter(Boolean);
    const figure = f => '<button class="thumb-button" data-view="'+escape(f.path)+'"><img src="'+escape(fileUrl(f))+'" loading="lazy" alt="'+escape(f.title)+'"><span>Ampliar '+escape(f.title.toLowerCase())+'</span></button>';
    return pageHead("Momento 1","Infraestructura","El inventario describe las máquinas que se crearían en Proxmox VE para separar almacenamiento, cómputo y balanceo.")+
      '<div class="section-note">Direccionamiento propuesto de las VM: <strong>'+escape(net.cidr)+'</strong> · Puente <strong>'+escape(net.bridge)+'</strong> · Gateway <strong>'+escape(net.gateway)+'</strong>.</div>'+
      '<div class="section-head"><h2>Inventario virtual</h2>'+linkButton("Ver pruebas","#evidencias","plain-button")+'</div>'+
      '<div class="tools" data-filters>'+searchField("Buscar máquina","Hostname, dirección IP o función")+'</div><div id="results">'+inventoryRows()+'</div>'+
      (figures.length ? '<div class="section-head"><h2>Diagramas de diseño</h2></div><div class="two-col">'+figures.map(figure).join("")+'</div>':"")+
      '<div class="section-head"><h2>Configuración reproducible</h2></div>'+fileList([bySuffix("configuracion-momento-1.zip"),fileMap.get("infrastructure/proxmox/inventory.json")].filter(Boolean));
  }
  function chip(status) {
    const value = norm(status);
    const cls = value==="implementado y verificado" ? "ok" : value.includes("bloque") || value.includes("simula") ? "caution" : value==="pendiente" ? "" : "progress";
    return '<span class="chip '+cls+'">'+escape(status)+'</span>';
  }
  function definition(pairs) {
    return '<dl class="definition">'+pairs.filter(([,value])=>value && value.trim()).map(([label,value])=>
      '<dt>'+escape(label)+'</dt><dd>'+escape(value)+'</dd>').join("")+'</dl>';
  }
  function requirementRows() {
    const query=norm(params.get("q")), selected=params.get("momento"), status=params.get("estado");
    const filtered=reqs.filter(row => (!selected || row.momento===selected) && (!status || row.estado===status) &&
      norm([row.id,row.requisito,row.tecnologia,row.archivo_asociado,row.evidencia_asociada].join(" ")).includes(query));
    return countLine("Requisitos coincidentes ·",filtered.length)+'<div class="list-rows">'+(filtered.length ? filtered.map(row => {
      const associated=data.files.filter(f=>f.references.includes(row.id));
      return '<details class="req"><summary><span class="key mono">'+escape(row.id)+'</span><strong>'+escape(row.requisito)+'</strong>'+chip(row.estado)+'<span class="arrow">'+icon("chevron")+'</span></summary><div class="details-body">'+definition([
        ["Página del PDF",row.pagina_pdf],["Momento",row.momento],["Obligatoriedad",row.obligatoriedad],
        ["Tecnología",row.tecnologia],["Implementación",row.metodo_implementacion],["Aceptación",row.criterio_aceptacion],
        ["Artefacto",row.archivo_asociado],["Evidencia",row.evidencia_asociada],["Limitaciones",row.limitaciones],["Observaciones",row.observaciones]
      ])+(associated.length ? linkButton("Consultar evidencia asociada",routeLink("evidencias",{q:row.id}),"plain-button"):"")+'</div></details>';
    }).join("") : empty())+'</div>';
  }
  function matrix() {
    const momentOrder = ["1","2","3","Transversal","Final"];
    const present = [...new Set(reqs.map(row=>row.momento))].sort((a,b)=>momentOrder.indexOf(a)-momentOrder.indexOf(b));
    const statuses = [...new Set(reqs.map(row=>row.estado))].sort();
    return pageHead("Requisitos del profesor","Matriz de trazabilidad","Cada fila vincula una exigencia del PDF con su criterio de aceptación, artefacto y evidencia disponible. Abra un requisito para revisar el detalle.")+
      '<div class="tools" data-filters>'+searchField("Buscar requisito","Identificador, tecnología o requisito")+
      selectField("Momento","momento",present.map(v=>[v,moments[v] ? "Momento "+v:v]))+selectField("Estado","estado",statuses.map(v=>[v,v]))+'</div><div id="results">'+requirementRows()+'</div>';
  }
  function component(file) {
    const parts=file.path.split("/");
    if(parts[0]==="evidence" && parts.length>=4) return parts[2];
    if(parts[0]==="evidence") return parts[1]==="block-00" ? "Bloque 0" : "Validación";
    return file.kind;
  }
  function fileMoment(file) {
    if(file.path.includes("/moment-02/") || ["Datos","SQL","Gobierno","Procesamiento"].includes(file.kind)) return "2";
    if(file.path.includes("/moment-03/") || file.kind==="Monitoreo") return "3";
    if(file.path.includes("/final/") || file.kind==="Sustentación") return "Final";
    if(file.path.includes("/moment-01/") || file.kind==="Infraestructura" || file.kind==="Diagrama") return "1";
    if(file.path.includes("/block-00/") || file.kind==="Bloque 0") return "0";
    return "Transversal";
  }
  function fileList(files, isEvidence=false) {
    if (!files.length) return empty();
    return '<div class="list-rows file-list">'+files.map(file => {
      const previewable = file.preview || ["PNG","SVG","JPG","PDF"].includes(file.format);
      const info = (isEvidence ? component(file)+" · ":"")+file.format+' · '+sizeName(file.size)+(file.references.length ? ' · '+file.references.join(', '):'');
      const image=["PNG","SVG","JPG"].includes(file.format);
      return '<div class="file"><span class="file-mark">'+icon(image ? "photo" : file.format==="ZIP"?"box":"doc")+'</span><div><span class="file-title">'+escape(file.title)+'</span><small class="file-sub">'+escape(info)+'</small></div><div class="actions">'+(previewable ? buttonView(file,"plain-button"):"")+download(file)+'</div></div>';
    }).join("")+'</div>';
  }
  function assetRows() {
    const evidence=section==="evidencias", query=norm(params.get("q")), pick=params.get("tipo"), moment=params.get("momento");
    const filtered=data.files.filter(file => (file.kind==="Evidencia")===evidence &&
      (!pick || (evidence ? component(file) : file.format)===pick) && (!moment || fileMoment(file)===moment) &&
      norm([file.path,file.title,file.format,...file.references].join(" ")).includes(query))
      .sort((a,b)=>a.title.localeCompare(b.title,"es") || a.path.localeCompare(b.path));
    return countLine("Archivos coincidentes ·",filtered.length)+fileList(filtered,evidence);
  }
  function assets(evidence) {
    const choices=[...new Set(data.files.filter(file=>(file.kind==="Evidencia")===evidence).map(file=>evidence ? component(file):file.format))].sort();
    const optionalRows = reqs.filter(row => /^M3-P[1-6]$/.test(row.id));
    const testsSummary= evidence && optionalRows.length ? '<div class="section-head"><h2>Pruebas obligatorias</h2></div><div class="list-rows table-wrap" tabindex="0" aria-label="Pruebas obligatorias del PDF"><table><thead><tr><th>Prueba</th><th>Requisito del PDF</th><th>Estado en la matriz</th></tr></thead><tbody>'+optionalRows.map(row=>'<tr><td><a href="'+escape(routeLink("trazabilidad",{q:row.id}))+'">'+escape(row.id)+'</a></td><td>'+escape(row.requisito)+'</td><td>'+chip(row.estado)+'</td></tr>').join("")+'</tbody></table></div>':"";
    return pageHead(evidence ? "Resultados del laboratorio":"Recursos de entrega",
      evidence ? "Evidencias":"Centro documental",
      evidence ? "Consulte las salidas conservadas por componente. Cada archivo incluye su tamaño y huella SHA-256 en la vista previa." :
      "Abra los informes y diagramas o descargue sus archivos originales para revisarlos sin conexión.")+
      '<div class="tools" data-filters>'+searchField("Buscar archivo",evidence?"Nombre, componente o requisito":"Título, nombre o formato")+
      selectField(evidence?"Componente":"Formato","tipo",choices.map(v=>[v,v]))+
      selectField("Momento","momento",[["0","Bloque 0"],["1","Momento 1"],["2","Momento 2"],["3","Momento 3"],["Final","Final"],["Transversal","Transversal"]])+'</div><div id="results">'+assetRows()+'</div>'+testsSummary;
  }
  function showFile(path, trigger) {
    const file=fileMap.get(path);
    if(!file) return;
    lastViewButton=trigger;
    document.querySelector("#viewer-kind").textContent=file.kind+" · "+file.format;
    document.querySelector("#viewer-title").textContent=file.title;
    const content=document.querySelector("#viewer-content");
    content.replaceChildren();
    if(["PNG","JPG","SVG"].includes(file.format)) {
      const img=document.createElement("img"); img.src=fileUrl(file); img.alt=file.title; content.append(img);
    } else if(file.format==="PDF") {
      const pdf=document.createElement("object"); pdf.type="application/pdf"; pdf.data=fileUrl(file);
      const message=document.createElement("p"); message.textContent="El lector integrado depende del navegador. También puede abrir el PDF en una pestaña."; pdf.append(message);content.append(pdf);
    } else {
      const pre=document.createElement("pre"); pre.textContent=file.preview || "Consulte el archivo original.";
      content.append(pre);
      if(file.truncated) { const p=document.createElement("p"); p.textContent="Vista previa de los primeros 24 000 bytes. El original contiene el texto completo."; content.append(p); }
    }
    const actions = (file.format==="PDF" ? '<a class="plain-button" target="_blank" rel="noopener" href="'+escape(fileUrl(file))+'">Abrir PDF '+icon("external")+'</a>' : '')+download(file);
    document.querySelector("#viewer-footer").innerHTML='<div>'+escape(file.path)+' · '+sizeName(file.size)+'<div class="hash">SHA-256 '+escape(file.sha256)+'</div></div><div class="actions">'+actions+'</div>';
    viewer.showModal();
    viewer.querySelector("[data-close]").focus();
  }
  const extras=window.createLakeViews({data,icon,esc:escape,norm,fmt,sizeName,fileUrl,fileMap,bySuffix,reqs,pageHead,linkButton,fileList,definition,chip,routeLink,buttonView,download,getParams:()=>params});
  const renderers={...extras.renderers,resumen:home,infraestructura:infra,trazabilidad:matrix,evidencias:()=>assets(true),documentos:()=>assets(false)};
  function menu(open) {
    document.querySelector("#rail").classList.toggle("open",open);
    document.querySelector(".mobile-open").setAttribute("aria-expanded",String(open));
    if(open) document.querySelector(".mobile-close").focus();
  }
  function render(moveFocus) {
    const hash=window.location.hash.slice(1).split("?");
    if(hash[0]==="contenido"){main.focus();return}
    section=Object.hasOwn(pages,hash[0]) ? hash[0] : "resumen";
    params=new URLSearchParams(hash[1] || "");
    menu(false);
    if(viewer.open) viewer.close();
    for(const nav of document.querySelectorAll("[data-section]")) {
      if(nav.dataset.section===section) nav.setAttribute("aria-current","page"); else nav.removeAttribute("aria-current");
    }
    document.querySelector("#section-name").textContent=pages[section];
    document.title=pages[section]+" · Lago de Datos Distribuido — Portal de Demostración del Proyecto";
    extras.stop();
    main.innerHTML=renderers[section]();
    if(moveFocus) { main.focus({preventScroll:true}); window.scrollTo(0,0); }
  }
  function filter(event) {
    const target=event.target;
    if(extras.change(section,event)) return;
    if(!target.closest("[data-filters]") || !target.name) return;
    if(target.value) params.set(target.name,target.value); else params.delete(target.name);
    history.replaceState(null,"",routeLink(section,Object.fromEntries(params)));
    const results=document.querySelector("#results");
    results.innerHTML=section==="trazabilidad" ? requirementRows() : section==="infraestructura" ? inventoryRows():assetRows();
  }
  main.addEventListener("input",filter);
  document.addEventListener("click",event=>{
    if(extras.click(section,event)) return;
    const view=event.target.closest("[data-view]");
    const toggle=event.target.closest("[data-menu]");
    if(view) showFile(view.dataset.view,view);
    if(toggle) { menu(toggle.dataset.menu==="open"); if(toggle.dataset.menu==="close") document.querySelector(".mobile-open").focus(); }
    if(event.target.closest("[data-close]") || event.target===viewer) viewer.close();
    if(event.target.closest(".rail a")) menu(false);
  });
  viewer.addEventListener("close",()=>{
    document.querySelector("#viewer-content").replaceChildren();
    if(lastViewButton?.isConnected) lastViewButton.focus();
  });
  document.addEventListener("keydown",event=>{
    if(event.key==="Escape" && document.querySelector("#rail.open")) {menu(false);document.querySelector(".mobile-open").focus();}
  });
  window.addEventListener("hashchange",()=>render(true));
  render(false);
})();
