import { buildQualification, cellPresentation, qualificationRegionEdges, stationSize } from "./qualification.mjs?v=20261117-104";
import { buildCcpcfQualification, ccpcfRegionEdges } from "./ccpcf-qualification.mjs?v=20261117-104";

function el(tag, className = "", text = "") {
  const element = document.createElement(tag);
  element.className = className;
  element.textContent = text;
  return element;
}

export function renderQualification(container, data, mode) {
  const ccpcf = mode === "ccpcf";
  const model = ccpcf ? buildCcpcfQualification(data) : buildQualification(data, mode);
  container.replaceChildren();
  container.classList.toggle("qualification-ecf", mode === "ecf");
  const heading = el("div", "section-heading");
  const titleBlock = el("div");
  titleBlock.append(el("p", "eyebrow", ccpcf ? "CCPC FINAL" : mode === "wf" ? "WORLD FINALS" : "EAST CONTINENT FINAL"));
  const title = el("h2", "", `${mode.toUpperCase()} 名额盘点`);
  title.id = "qualification-title";
  titleBlock.append(title);
  const headingNote = el("p", "section-note", `2026–2027 赛季 · 截至 ${data.asOf}`);
  const ruleLink = el("a", "qualification-rule-link", "查看规则");
  ruleLink.href = data.rules[mode === "ecf" ? 1 : 0].url;
  ruleLink.target = "_blank";
  ruleLink.rel = "noopener noreferrer";
  heading.append(titleBlock, headingNote);
  const disclaimer = el("p", "qualification-disclaimer", data.disclaimer);
  disclaimer.setAttribute("role", "note");
  const legend = el("div", "qualification-legend");
  legend.setAttribute("aria-label", "颜色图例");
  const pressureDefinitions = {
    "pressure-low": "低：潜在竞争位置全部新增占位，仍有足够名额。",
    "pressure-medium": "中：潜在竞争位置中，超过一半新增占位，才会触及名额限制。",
    "pressure-high": "高：潜在竞争位置中，一半或更少新增占位，就会触及名额限制。",
  };
  for (const [kind, label] of [["safe", "确定出线"], ["pressure-low", "待定出线 · 占位压力低"], ["pressure-medium", "待定出线 · 占位压力中"], ["pressure-high", "待定出线 · 占位压力高"], ["candidate", "出线区域可选队伍"], ["outside", "未出线"], ["duplicate", "重复 / 达上限"], ["pending", "待赛"]]) {
    if (mode !== "wf" && kind === "candidate") continue;
    const key = el("span", `qualification-key qualification-${kind}`, label);
    if (ccpcf && kind === "duplicate") key.textContent = "重复";
    if (pressureDefinitions[kind]) {
      key.title = pressureDefinitions[kind];
    }
    legend.append(key);
  }
  const regionKey = el("span", "qualification-key qualification-region-key", "粗框：当前出线区域");
  regionKey.title = "按已知成绩逐行遍历至当前截止位置；框内包含重复队伍与待赛空位，不表示每格都获名额。";
  if (!ccpcf) legend.append(regionKey);
  if (ccpcf) {
    for (const channel of model.channels) {
      const label = channel.number === 1 ? "实线框：第一名额出线区域" : "虚线框：第二名额出线区域";
      const key = el("span", `qualification-key qualification-channel-${channel.number}-key`, label);
      key.title = "按本渠道入选学校的最佳站内名次划定，包含边界并列；框内可能有重复队伍或待赛空位，不表示每格都获名额。";
      legend.append(key);
    }
  }
  if (mode === "ecf") {
    const rankKey = el("span", "qualification-key qualification-rank-key", "校内顺位（仅当前出线队伍）");
    rankKey.title = "同校队伍按遍历先后排序：第 1 队、第 2 队、第 3 队（达到每校 3 队上限）。";
    for (const n of [1, 2, 3]) rankKey.append(el("span", `qualification-school-rank school-rank-${n}`, `校内 ${n}`));
    legend.append(rankKey);
  }
  if (mode === "wf") {
    const hostKey = el("span", "qualification-key qualification-host-key", "承办学校资格：其他站校排前 10");
    hostKey.title = "标记达到普通区域赛成绩门槛的格子；Hosting Team 名额仍待申请与资格核验。";
    legend.append(hostKey);
  }
  const channels = el("div", "qualification-channels");
  const quotaBox = items => {
    const box = el("div", "qualification-channel");
    const channelHeading = el("div", "qualification-channel-heading");
    channelHeading.append(el("h3", "", "名额类别"), ruleLink);
    box.append(channelHeading);
    const list = el("ul", "qualification-quota-list");
    for (const [name, count, description, excluded = false] of items) {
      const li = el("li");
      li.append(el("strong", "", `${name}${excluded ? "（本页不包含）" : ""} · ${count}`), el("span", "", description));
      list.append(li);
    }
    box.append(list);
    channels.append(box);
  };
  if (mode === "wf") {
    quotaBox([
      ["区域赛", `${model.quota} 个`, "按各站高校排名轮流分配，同校只计一次。"],
      ["EC Final", `${16 - model.quota - 3}–${16 - model.quota} 个`, "按 EC Final 高校排名分配，跳过已晋级学校。"],
      ["承办优惠", "0–2 个", "分配给满足成绩与申请条件的承办高校。"],
      ["港澳保底", "0–1 个", "其他渠道无港澳高校晋级时，择优分配。"],
    ]);
  } else if (ccpcf) {
    quotaBox(model.channels.map(channel => [
      `学校第 ${channel.number} 名额`, `前 ${channel.quota} 名（含并列）`,
      channel.number === 1 ? "各校最佳队伍按全国赛最好名次排名。" : "各校第二支独立队伍按全国赛最好名次排名。",
    ]).concat([
      ["女生专场", "≤5 个", "按女生赛学校排名分配，仅限女队参赛。", true],
      ["高职高专", "≤5 个", "按高职赛学校排名分配，仅限专科队参赛。", true],
      ["承办奖励", "每校 1 个", "分配给未从成绩渠道获得名额的相关赛事承办高校。", true],
      ["港澳台及海外学校", "每校 ≤2 个", "面向参加比赛的香港、澳门、台湾及海外高校。", true],
    ]));
  } else {
    quotaBox([
      ["大陆赛站成绩", `${model.quota} 个`, `按大陆赛站成绩逐行录取，每校最多 ${model.cap} 队。`],
      ["香港第二轮", "≤10 个", "按香港站获奖队伍名次补充录取。"],
      ["贡献奖励", "≤40 个", "奖励近三年晋级 WF 的高校及当年区域赛承办、出题高校。", true],
      ["激励", "≤10 个", "从剩余名额中分配给未获成绩或贡献奖励名额的高校，每校最多 1 个。", true],
    ]);
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
    const option = el("option", "", ccpcf && value === "boundary" ? "当前入围成绩及附近" : text);
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
  const caption = el("caption", "visually-hidden", ccpcf
    ? "各站正式队伍按成绩排列，跨站合并成员重叠队伍后按最好名次分配学校名额；赛站按日期排列。"
    : `${mode === "wf" ? "高校" : "队伍"}排名逐行分配，赛站按有效规模从大到小排列。`);
  table.append(caption);
  const columns = el("colgroup");
  columns.append(el("col", "qualification-rank-column"));
  for (let i = 0; i < model.stations.length; i++) columns.append(el("col"));
  if (mode === "wf" || model.hongkong) columns.append(el("col"));
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
      el("span", `qualification-size ${station.status === "pending" ? "is-estimate" : ""}`, ccpcf
        ? station.status === "pending" ? "待赛" : `${station.officialCount} 支正式队`
        : `${station.status === "pending" ? "估计 " : ""}${stationSize(station)} 队`),
      el("small", "", station.date.slice(5)));
    header.append(th);
  }
  if (mode === "wf") {
    const finalHeader = el("th", "qualification-final-header", "EC Final");
    finalHeader.scope = "col";
    finalHeader.append(el("small", "", "待赛"));
    header.append(finalHeader);
  }
  if (model.hongkong) {
    const hk = model.hongkong;
    const hkHeader = el("th", "qualification-final-header");
    hkHeader.scope = "col";
    hkHeader.append(el("span", "qualification-station-title", hk.title),
      el("span", `qualification-size ${hk.status === "pending" ? "is-estimate" : ""}`, `${hk.status === "pending" ? "估计 " : ""}${stationSize(hk)} 队`),
      el("small", "", `${hk.date.slice(5)} · 第二轮`));
    header.append(hkHeader);
  }
  head.append(header);
  const body = el("tbody");
  table.append(head, body);
  shell.append(table);
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
    const count = query || scope.value === "all" ? model.maxRows : Math.min(model.maxRows, Math.max(mode === "wf" ? 10 : 5, model.boundaryRow + 3));
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
          const matchesQuery = query && [cell.team.school, cell.team.name, ...cell.team.members, cell.searchText ?? ""].some(s => s.toLocaleLowerCase().includes(query));
          if (matchesQuery) { td.classList.add("qualification-match"); matches.push(td); }
          else if (query) td.classList.add("qualification-dim");
          const card = el("div", "qualification-team");
          const badge = el("span", "qualification-badge", presentation.label);
          if (ccpcf && cell.role === "duplicate") badge.textContent = "重复";
          if (ccpcf) badge.title = cell.reason;
          const identity = el("div", "qualification-team-heading");
          const school = el("strong", "qualification-school", cell.team.school);
          const name = el("span", "qualification-team-name", cell.team.name);
          const members = el("small", "qualification-members", cell.team.members.join(" · "));
          for (const item of [school, name, members]) item.title = item.textContent;
          const tags = el("div", "qualification-tags");
          if (cell.schoolRank && cell.role === "selected") {
            const rankTag = el("span", `qualification-school-rank school-rank-${Math.min(cell.schoolRank, 3)}`, ccpcf ? `第 ${cell.schoolRank} 名额` : `校内 ${cell.schoolRank}`);
            rankTag.title = ccpcf ? `本渠道第 ${cell.channelRank} 名；名额归学校` : `校内顺位：${cell.team.school}第 ${cell.schoolRank} 支队伍`;
            tags.append(rankTag);
          }
          if (cell.hosting) {
            td.classList.add("qualification-host-performance");
            badge.textContent = "承办学校资格";
            badge.classList.add("qualification-host-mark");
            badge.title = `承办${cell.hosting.stations.join("、")}站；${station.title}站校排第 ${cell.hosting.schoolRank}，达到普通区域赛成绩门槛，优惠资格待核验。`;
          }
          tags.append(badge);
          identity.append(school, tags);
          card.append(identity, name, members);
          if (ccpcf) card.append(el("small", "qualification-members", `本站 #${cell.team.rank} · 合并后最佳 #${cell.bestRank}`));
          td.append(card);
        } else td.append(el("span", "qualification-placeholder", "—"));
        for (const edge of qualificationRegionEdges(position, model.stations.length, model.current.frontier)) {
          td.classList.add("qualification-region-edge", `qualification-region-${edge}`);
        }
        if (ccpcf) {
          for (const channel of model.channels) {
            for (const edge of ccpcfRegionEdges(row, column, channel.regionRows)) {
              td.classList.add(`qualification-channel-${channel.number}`, `qualification-channel-${channel.number}-${edge}`);
            }
          }
        }
        tr.append(td);
      }
      if (mode === "wf" || model.hongkong) {
        const td = el("td", "qualification-pending qualification-final");
        if (row === 0) td.append(el("span", "", "待结果"));
        tr.append(td);
      }
      fragment.append(tr);
    }
    body.replaceChildren(fragment);
    previous.disabled = next.disabled = matches.length === 0;
    result.textContent = query ? "0 个匹配位置" : ccpcf ? `显示 ${count} 行` : `显示 ${count} 行 · 出线区域至第 ${model.boundaryRow} 行`;
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
  container.append(heading, disclaimer, legend, toolbar, shell, channels);
  draw();
  return model;
}
