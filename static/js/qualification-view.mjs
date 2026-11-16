import { buildQualification, cellPresentation, qualificationRegionEdges, stationSize } from "./qualification.mjs?v=20261116-95";

function el(tag, className = "", text = "") {
  const element = document.createElement(tag);
  element.className = className;
  element.textContent = text;
  return element;
}

export function renderQualification(container, data, mode) {
  const model = buildQualification(data, mode);
  container.replaceChildren();
  container.classList.toggle("qualification-ecf", mode === "ecf");
  const heading = el("div", "section-heading");
  const titleBlock = el("div");
  titleBlock.append(el("p", "eyebrow", mode === "wf" ? "WORLD FINALS" : "EAST CONTINENT FINAL"));
  const title = el("h2", "", mode === "wf" ? "WF 名额盘点" : "ECF 名额盘点");
  title.id = "qualification-title";
  titleBlock.append(title);
  heading.append(titleBlock, el("p", "section-note", `2026–2027 赛季 · 截至 ${data.asOf}`));
  const disclaimer = el("p", "qualification-disclaimer", data.disclaimer);
  disclaimer.setAttribute("role", "note");
  const legend = el("div", "qualification-legend");
  legend.setAttribute("aria-label", "颜色图例");
  const pressureDefinitions = {
    "pressure-low": "低：前方未赛位置全部新增占位，仍有足够的总名额；具体资格还受同校竞争等因素影响。",
    "pressure-medium": "中：前方超过一半的未赛位置新增占位，才会触及总名额限制。",
    "pressure-high": "高：前方一半或更少的未赛位置新增占位，就会触及总名额限制。",
  };
  for (const [kind, label] of [["safe", "确定有名额"], ["pressure-low", "待定 · 占位压力低"], ["pressure-medium", "待定 · 占位压力中"], ["pressure-high", "待定 · 占位压力高"], ["candidate", "出线区域可选队伍"], ["duplicate", "重复 / 达上限"], ["outside", "当前未出线"], ["pending", "待赛"]]) {
    if (mode === "ecf" && kind === "candidate") continue;
    const key = el("span", `qualification-key qualification-${kind}`, label);
    if (pressureDefinitions[kind]) {
      key.title = pressureDefinitions[kind];
    }
    legend.append(key);
  }
  const regionKey = el("span", "qualification-key qualification-region-key", "粗框：当前出线区域");
  regionKey.title = "按已知成绩逐行遍历至当前截止位置；框内包含重复队伍与待赛空位，不表示每格都获名额。";
  legend.append(regionKey);
  if (mode === "wf") {
    const hostKey = el("span", "qualification-key qualification-host-key", "承办学校：其他站校排前 10");
    hostKey.title = "标记达到普通区域赛成绩门槛的格子；Hosting Team 名额仍待申请与资格核验。";
    legend.append(hostKey);
  }
  const channels = el("div", "qualification-channels");
  if (mode === "wf") {
    const trial = el("div", "qualification-channel");
    trial.append(el("h3", "", "EC Final 与其他渠道"));
    trial.append(el("p", "section-note", `本页按 WF 总名额 16 个盘点：区域赛 ${model.quota} 个，EC Final ${16 - model.quota - 3}–${16 - model.quota} 个（扣除承办优惠 0–2 个及港澳保底 0–1 个）。其余渠道待结果与资格核验。`));
    channels.append(trial);
  } else {
    const box = el("div", "qualification-channel");
    box.append(el("h3", "", "其余资格分开盘点"), el("p", "section-note", "香港第二轮最多 10 个资格，限金银铜牌队，须核验第一轮报名成员与学校上限。贡献奖励 ≤40、激励 ≤10，受正式名额总数 280 约束；申请与报名名单未齐，暂不分配到队伍。"));
    channels.append(box);
  }
  const toolbar = el("div", "qualification-toolbar");
  const searchLabel = el("label", "", "查找学校、队名或成员");
  const search = document.createElement("input");
  search.type = "search";
  search.placeholder = "查找并突出显示，保留原顺位";
  search.setAttribute("aria-label", "盘点搜索学校队伍成员");
  searchLabel.append(search);
  const scopeLabel = el("label", "", "显示范围");
  const scope = document.createElement("select");
  scope.setAttribute("aria-label", "盘点显示范围");
  for (const [value, text] of [["boundary", "出线区域及附近"], ["all", "完整榜单"]]) {
    const option = el("option", "", text);
    option.value = value;
    scope.append(option);
  }
  scopeLabel.append(scope);
  const result = el("p", "section-note");
  result.setAttribute("aria-live", "polite");
  const navigation = el("div", "qualification-search-navigation");
  const previous = el("button", "", "↑");
  const next = el("button", "", "↓");
  for (const [button, label] of [[previous, "上一个搜索结果"], [next, "下一个搜索结果"]]) {
    button.type = "button";
    button.setAttribute("aria-label", label);
    button.title = label;
  }
  navigation.append(previous, next);
  toolbar.append(searchLabel, navigation, scopeLabel, result);
  const shell = el("div", "qualification-scroll");
  shell.id = "qualification-scroll";
  shell.tabIndex = 0;
  shell.setAttribute("aria-label", "名额盘点表，可横向和纵向滚动");
  const table = el("table", "qualification-table");
  const caption = el("caption", "visually-hidden", `${mode === "wf" ? "高校" : "队伍"}排名逐行分配，赛站按有效规模从大到小排列。`);
  table.append(caption);
  const columns = el("colgroup");
  columns.append(el("col", "qualification-rank-column"));
  for (let i = 0; i < model.stations.length; i++) columns.append(el("col"));
  if (mode === "wf") columns.append(el("col"));
  table.append(columns);
  const head = el("thead");
  const header = el("tr");
  const rankHeader = el("th", "qualification-row-rank", mode === "wf" ? "校排" : "顺位");
  rankHeader.scope = "col";
  header.append(rankHeader);
  for (const station of model.stations) {
    const th = el("th");
    th.scope = "col";
    th.append(el("span", "qualification-station-title", station.title),
      el("span", `qualification-size ${station.status === "pending" ? "is-estimate" : ""}`, `${station.status === "pending" ? "估计 " : ""}${stationSize(station)} 队`),
      el("small", "", station.date.slice(5)));
    header.append(th);
  }
  if (mode === "wf") {
    const finalHeader = el("th", "qualification-final-header", "EC Final");
    finalHeader.scope = "col";
    finalHeader.append(el("small", "", "待赛"));
    header.append(finalHeader);
  }
  head.append(header);
  const body = el("tbody");
  table.append(head, body);
  shell.append(table);
  const hint = el("p", "qualification-scroll-hint", "点击队伍展开完整信息、占位压力与判定原因");
  let matches = [];
  let activeMatch = -1;
  const navigate = step => {
    if (!matches.length) return;
    matches[activeMatch]?.classList.remove("qualification-match-active");
    activeMatch = (activeMatch + step + matches.length) % matches.length;
    const cell = matches[activeMatch];
    cell.classList.add("qualification-match-active");
    // Scroll only the table so the search controls remain in place.
    const top = cell.offsetTop - head.offsetHeight;
    if (top < shell.scrollTop || cell.offsetTop + cell.offsetHeight > shell.scrollTop + shell.clientHeight) shell.scrollTop = top;
    const left = cell.offsetLeft - rankHeader.offsetWidth;
    if (left < shell.scrollLeft || cell.offsetLeft + cell.offsetWidth > shell.scrollLeft + shell.clientWidth) shell.scrollLeft = left;
    result.textContent = `${activeMatch + 1} / ${matches.length} 个匹配位置`;
  };
  const draw = () => {
    const query = search.value.trim().toLocaleLowerCase();
    const count = query || scope.value === "all" ? model.maxRows : Math.min(model.maxRows, Math.max(5, model.boundaryRow + 3));
    matches = [];
    activeMatch = -1;
    const fragment = document.createDocumentFragment();
    for (let row = 0; row < count; row++) {
      const tr = el("tr");
      const rank = el("th", "qualification-row-rank", String(row + 1));
      rank.scope = "row";
      tr.append(rank);
      for (const [column, station] of model.stations.entries()) {
        const position = row * model.stations.length + column;
        const cell = model.cells.get(position);
        const td = el("td");
        if (station.status === "pending") {
          td.className = "qualification-pending";
          if (row === 0) td.append(el("span", "", "待结果"));
          else td.append(el("span", "qualification-placeholder", "—"));
        } else if (cell) {
          const presentation = cellPresentation(cell);
          td.className = `qualification-${presentation.className}`;
          td.dataset.role = cell.role;
          td.dataset.certainty = cell.certainty ?? "";
          td.dataset.pressure = cell.pressure?.level ?? "";
          const matchesQuery = query && [cell.team.school, cell.team.name, ...cell.team.members].some(s => s.toLocaleLowerCase().includes(query));
          if (matchesQuery) { td.classList.add("qualification-match"); matches.push(td); }
          else if (query) td.classList.add("qualification-dim");
          const card = el("details", "qualification-team");
          const summary = el("summary");
          const badge = el("span", "qualification-badge", presentation.label);
          const identity = el("div", "qualification-team-heading");
          const school = el("strong", "qualification-school", cell.team.school);
          const name = el("span", "qualification-team-name", cell.team.name);
          const members = el("small", "qualification-members", cell.team.members.join(" · "));
          for (const item of [school, name, members]) item.title = item.textContent;
          const schoolLine = el("div", "qualification-school-line");
          schoolLine.append(school);
          let hostNote = "";
          if (cell.hosting) {
            td.classList.add("qualification-host-performance");
            hostNote = `${cell.team.school}承办${cell.hosting.stations.join("、")}站，在其他赛站（${station.title}）取得校排第 ${cell.hosting.schoolRank}，达到普通区域赛前 10 的成绩门槛。Hosting Team 每年最多 2 校；申请、连续两年享用限制及 EC Final 顺位仍待核验，已通过 A/B 晋级的高校不占此名额。`;
            const host = el("span", "qualification-host-mark", "承办学校");
            host.title = `承办${cell.hosting.stations.join("、")}站；${station.title}站校排第 ${cell.hosting.schoolRank}，达到普通区域赛成绩门槛，优惠资格待核验。`;
            schoolLine.append(host);
          }
          identity.append(schoolLine, badge);
          summary.append(identity, name, members);
          const info = el("p", "qualification-cell-reason", `${presentation.detail} · 原榜 #${cell.team.rank} · ${cell.team.solved} 题。${cell.reason}`);
          if (hostNote) info.append(el("span", "qualification-host-detail", hostNote));
          if (cell.pressure) {
            const pressure = cell.pressure;
            const schoolNote = pressure.schoolTolerance === null ? "" : `同校还可先新增 ${pressure.schoolTolerance} 支不同队伍；${pressure.schoolRisk ? "未排除同校竞争" : "同校上限不构成风险"}。`;
            info.append(el("span", "qualification-pressure-detail", `占位压力${{ low: "低", medium: "中", high: "高" }[pressure.level]}：仅考虑新增且不重复的有效占位时，还可承受 ${pressure.slotTolerance} 个；前面最多有 ${pressure.pendingBefore} 个未赛位置。${schoolNote}这不是出线概率，不含后续自身成绩改善。`));
            badge.title = info.textContent;
          }
          card.append(summary, info);
          td.append(card);
        } else td.append(el("span", "qualification-placeholder", "—"));
        for (const edge of qualificationRegionEdges(position, model.stations.length, model.current.frontier)) {
          td.classList.add("qualification-region-edge", `qualification-region-${edge}`);
        }
        tr.append(td);
      }
      if (mode === "wf") {
        const td = el("td", "qualification-pending qualification-final");
        if (row === 0) td.append(el("span", "", "待结果"));
        tr.append(td);
      }
      fragment.append(tr);
    }
    body.replaceChildren(fragment);
    previous.disabled = next.disabled = matches.length === 0;
    result.textContent = query ? "0 个匹配位置" : `显示 ${count} 行 · 出线区域至第 ${model.boundaryRow} 行`;
    if (matches.length) navigate(1);
  };
  previous.addEventListener("click", () => navigate(-1));
  next.addEventListener("click", () => navigate(1));
  search.addEventListener("keydown", event => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    navigate(event.shiftKey ? -1 : 1);
  });
  search.addEventListener("input", draw);
  scope.addEventListener("change", draw);
  container.append(heading, disclaimer, legend, toolbar, hint, shell, channels);
  draw();
  return model;
}
