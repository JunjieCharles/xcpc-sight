import {
  carriedRatings,
  createDataStore,
  formatDelta,
  ratingTier,
  ratingTimeline,
  readQueryState,
  searchCompetitors,
  writeQueryState,
} from "./data.mjs";

const ROW_HEIGHT = 44;
const OVERSCAN = 8;
const INDEX_URL = new URL("../data/index.json", import.meta.url).href;
const store = createDataStore(INDEX_URL);
const elements = {
  seriesSelect: document.querySelector("#series-select"),
  searchInput: document.querySelector("#search-input"),
  resultCount: document.querySelector("#result-count"),
  status: document.querySelector("#status"),
  seriesView: document.querySelector("#series-view"),
  seriesTitle: document.querySelector("#series-title"),
  seriesSummary: document.querySelector("#series-summary"),
  seriesHead: document.querySelector("#series-head"),
  seriesBody: document.querySelector("#series-body"),
  seriesScroll: document.querySelector("#series-scroll"),
  detailView: document.querySelector("#detail-view"),
  errorTemplate: document.querySelector("#error-template"),
};

const state = { seriesId: "", query: "", contestId: "", competitorId: "", series: null, index: null, filtered: [], renderFrame: 0 };

function node(tag, properties = {}, children = []) {
  const element = document.createElement(tag);
  for (const [key, value] of Object.entries(properties)) {
    if (key === "className") element.className = value;
    else if (key === "text") element.textContent = value;
    else if (key.startsWith("aria-")) element.setAttribute(key, value);
    else element[key] = value;
  }
  for (const child of children) element.append(child);
  return element;
}

function ratingNode(rating, className = "") {
  const tier = ratingTier(rating);
  const value = String(rating);
  const ratingElement = node("span", { className: ["rating-value", tier.className, className].filter(Boolean).join(" ") });
  if (tier.legendary) {
    ratingElement.append(
      node("span", { className: "rating-legendary-first", text: value[0] }),
      document.createTextNode(value.slice(1)),
    );
  } else {
    ratingElement.textContent = value;
  }
  return ratingElement;
}

function deltaNode(delta) {
  return node("span", {
    className: delta > 0 ? "positive" : delta < 0 ? "negative" : "delta-zero",
    text: `(${formatDelta(delta)})`,
  });
}

function columnGroup(widths) {
  const group = node("colgroup");
  widths.forEach((width) => {
    const column = node("col");
    column.style.width = `${width}px`;
    group.append(column);
  });
  return group;
}

function setUrl(mode = "replace") {
  const url = writeQueryState(location.href, {
    series: state.seriesId,
    query: state.query,
    contest: state.contestId,
    competitor: state.competitorId,
  });
  history[mode === "push" ? "pushState" : "replaceState"](null, "", `${url.pathname}${url.search}${url.hash}`);
}

function showError(error) {
  console.error(error);
  elements.status.hidden = true;
  elements.seriesView.hidden = true;
  elements.detailView.hidden = false;
  elements.detailView.replaceChildren();
  const panel = elements.errorTemplate.content.firstElementChild.cloneNode(true);
  panel.querySelector("p").textContent = error instanceof Error ? error.message : String(error);
  panel.querySelector("button").addEventListener("click", () => location.reload());
  elements.detailView.append(panel);
}

function spacer(height, columns) {
  const row = node("tr", { className: "virtual-spacer" });
  row.style.setProperty("--spacer-height", `${height}px`);
  row.append(node("td", { colSpan: columns, "aria-hidden": "true" }));
  return row;
}

function renderVirtualRows({ container, body, items, columns, createRow }) {
  const visible = Math.ceil(container.clientHeight / ROW_HEIGHT);
  const start = Math.max(0, Math.floor(container.scrollTop / ROW_HEIGHT) - OVERSCAN);
  const end = Math.min(items.length, start + visible + OVERSCAN * 2);
  const fragment = document.createDocumentFragment();
  if (start) fragment.append(spacer(start * ROW_HEIGHT, columns));
  for (let index = start; index < end; index += 1) fragment.append(createRow(items[index], index));
  if (end < items.length) fragment.append(spacer((items.length - end) * ROW_HEIGHT, columns));
  body.replaceChildren(fragment);
}

function scheduleSeriesRows() {
  cancelAnimationFrame(state.renderFrame);
  state.renderFrame = requestAnimationFrame(renderSeriesRows);
}

function personButton(competitor) {
  const button = node("button", { className: "link-button person", type: "button" }, [
    node("span", { text: competitor.member }),
    node("small", { text: competitor.school }),
  ]);
  button.addEventListener("click", () => openCompetitor(competitor.id));
  return button;
}

function renderSeriesRows() {
  if (!state.series) return;
  const columns = state.series.contests.length + 4;
  renderVirtualRows({
    container: elements.seriesScroll,
    body: elements.seriesBody,
    items: state.filtered,
    columns,
    createRow(competitor, index) {
      const row = node("tr");
      row.dataset.competitorId = competitor.id;
      row.setAttribute("aria-rowindex", String(index + 2));
      row.append(node("td", { text: String(competitor.rank) }));
      row.append(node("td", {}, [personButton(competitor)]));
      row.append(node("td", {}, [ratingNode(competitor.finalRating)]));
      row.append(node("td", { text: String(competitor.contestsParticipated) }));
      const participationByContest = new Map(competitor.participations.map((item) => [item.contestIndex, item]));
      const ratings = carriedRatings(competitor, state.series.contests.length, state.series.initialRating);
      ratings.forEach((rating, contestIndex) => {
        const participation = participationByContest.get(contestIndex);
        const cell = node("td", {
          className: participation ? "rating-participated" : "rating-absent",
          title: participation ? `已参赛，变化 ${formatDelta(participation.delta)}` : "本场未参加，Rating 沿用",
        }, [ratingNode(rating)]);
        if (participation) cell.append(" ", deltaNode(participation.delta));
        row.append(cell);
      });
      return row;
    },
  });
  elements.seriesBody.closest("table").setAttribute("aria-rowcount", String(state.filtered.length + 1));
}

function renderSeriesHeader() {
  const row = node("tr");
  row.append(node("th", { scope: "col", text: "排名" }));
  row.append(node("th", { scope: "col", text: "选手 / 学校" }));
  row.append(node("th", { scope: "col", text: "最终 Rating" }));
  row.append(node("th", { scope: "col", text: "参赛" }));
  state.series.contests.forEach((contest) => {
    const button = node("button", { type: "button", className: "contest-button", text: contest.title, title: contest.title });
    button.addEventListener("click", () => openContest(contest.id));
    row.append(node("th", { scope: "col" }, [button]));
  });
  elements.seriesHead.replaceChildren(row);
  const table = elements.seriesHead.closest("table");
  table.querySelector("colgroup")?.remove();
  table.prepend(columnGroup([62, 220, 104, 76, ...state.series.contests.map(() => 136)]));
  table.style.width = `${462 + state.series.contests.length * 136}px`;
}

function applySearch({ resetScroll = true } = {}) {
  state.query = elements.searchInput.value;
  state.filtered = searchCompetitors(state.series.competitors, state.query);
  elements.resultCount.textContent = `${state.filtered.length.toLocaleString("zh-CN")} 位选手`;
  if (resetScroll) elements.seriesScroll.scrollTop = 0;
  scheduleSeriesRows();
  setUrl();
}

function showSeries() {
  state.contestId = "";
  state.competitorId = "";
  elements.detailView.hidden = true;
  elements.seriesView.hidden = false;
  elements.seriesTitle.textContent = state.series.title;
  elements.seriesSummary.textContent = `${state.series.contests.length} 场比赛 · ${state.series.competitors.length.toLocaleString("zh-CN")} 位选手`;
  renderSeriesHeader();
  applySearch({ resetScroll: false });
}

function backButton() {
  const button = node("button", { className: "back-button", type: "button", text: "返回系列" });
  button.addEventListener("click", () => {
    state.contestId = "";
    state.competitorId = "";
    setUrl("push");
    showSeries();
  });
  return button;
}

function openContest(contestId, updateUrl = true) {
  const contestIndex = state.series.contests.findIndex((contest) => contest.id === contestId);
  if (contestIndex < 0) return showSeries();
  const contest = state.series.contests[contestIndex];
  const participants = state.index.participantsByContest[contestIndex];
  state.contestId = contest.id;
  state.competitorId = "";
  if (updateUrl) setUrl("push");
  elements.seriesView.hidden = true;
  elements.detailView.hidden = false;
  elements.detailView.replaceChildren();

  const heading = node("div", { className: "detail-header" }, [
    node("div", {}, [
      node("p", { className: "eyebrow", text: "CONTEST" }),
      node("h2", { id: "detail-title", text: contest.title, tabIndex: -1 }),
      node("p", { className: "detail-meta" }, [
        node("span", { text: new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(contest.startAt)) }),
        node("span", { text: `${participants.length.toLocaleString("zh-CN")} 位参赛者` }),
      ]),
    ]),
    backButton(),
  ]);
  const shell = node("div", { className: "table-shell contest-table-shell", tabIndex: 0, "aria-label": "本场参赛者表" });
  const headRow = node("tr");
  ["比赛排名", "选手 / 学校", "赛前", "赛后", "变化"].forEach((label) => headRow.append(node("th", { scope: "col", text: label })));
  const body = node("tbody");
  const table = node("table", { className: "data-table fixed-table contest-table" }, [
    columnGroup([96, 250, 90, 90, 90]),
    node("thead", {}, [headRow]),
    body,
  ]);
  table.style.minWidth = "616px";
  shell.append(table);
  const draw = () => renderVirtualRows({
    container: shell, body, items: participants, columns: 5,
    createRow({ competitor, participation }, index) {
      const row = node("tr");
      row.setAttribute("aria-rowindex", String(index + 2));
      row.append(node("td", { text: String(participation.contestRank) }));
      row.append(node("td", {}, [personButton(competitor)]));
      row.append(node("td", {}, [ratingNode(participation.before)]));
      row.append(node("td", {}, [ratingNode(participation.after)]));
      row.append(node("td", { className: participation.delta > 0 ? "positive" : participation.delta < 0 ? "negative" : "", text: formatDelta(participation.delta) }));
      return row;
    },
  });
  shell.addEventListener("scroll", () => requestAnimationFrame(draw), { passive: true });
  table.setAttribute("aria-rowcount", String(participants.length + 1));
  elements.detailView.append(heading, shell);
  draw();
  heading.querySelector("h2").focus?.();
}

function svgNode(tag, attributes = {}) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
  return element;
}

function ratingChart(competitor) {
  const points = ratingTimeline(competitor, state.series.contests, state.series.initialRating);
  const width = 760, height = 330, left = 54, right = 22, top = 24, bottom = 56;
  const ratings = points.map((point) => point.rating);
  const rawMin = Math.min(...ratings), rawMax = Math.max(...ratings);
  const pad = Math.max(50, Math.ceil((rawMax - rawMin) * .12));
  const min = Math.floor((rawMin - pad) / 50) * 50;
  const max = Math.ceil((rawMax + pad) / 50) * 50 || min + 100;
  const x = (index) => left + (points.length === 1 ? (width - left - right) / 2 : index * (width - left - right) / (points.length - 1));
  const y = (rating) => top + (max - rating) * (height - top - bottom) / (max - min);
  const figure = node("figure");
  const wrap = node("div", { className: "chart-wrap" });
  const svg = svgNode("svg", { class: "rating-chart", viewBox: `0 0 ${width} ${height}`, role: "img", "aria-labelledby": "chart-title chart-desc" });
  const title = svgNode("title", { id: "chart-title" }); title.textContent = `${competitor.member} 的系列 Rating 曲线`;
  const desc = svgNode("desc", { id: "chart-desc" }); desc.textContent = `覆盖系列全部 ${points.length} 场比赛，实际参赛显示标记，未参赛时延续当时 Rating。`;
  svg.append(title, desc);
  for (let i = 0; i <= 4; i += 1) {
    const value = Math.round((min + (max - min) * i / 4) / 10) * 10;
    const gridY = y(value);
    svg.append(svgNode("line", { class: "chart-grid", x1: left, x2: width - right, y1: gridY, y2: gridY }));
    const label = svgNode("text", { class: "chart-axis", x: left - 9, y: gridY + 4, "text-anchor": "end" }); label.textContent = String(value); svg.append(label);
  }
  for (let index = 1; index < points.length; index += 1) {
    const tier = ratingTier(points[index].rating);
    svg.append(svgNode("line", {
      class: "chart-line",
      x1: x(index - 1), y1: y(points[index - 1].rating),
      x2: x(index), y2: y(points[index].rating),
      stroke: tier.color,
    }));
  }
  const focus = svgNode("line", { class: "chart-focus", x1: 0, x2: 0, y1: top, y2: height - bottom, visibility: "hidden" });
  svg.append(focus);
  const tooltip = node("div", { className: "chart-tooltip", hidden: true, role: "status" });
  points.forEach((point, index) => {
    const participation = point.participation;
    if (point.participated) {
      const tier = ratingTier(point.rating);
      svg.append(svgNode("circle", { class: "chart-dot", cx: x(index), cy: y(point.rating), r: 4, stroke: tier.color }));
    }
    const detail = participation
      ? `#${participation.contestRank}，${participation.before} → ${participation.after} (${formatDelta(participation.delta)})`
      : "未参赛";
    const hit = svgNode("rect", {
      class: "chart-hit",
      x: index === 0 ? left : (x(index - 1) + x(index)) / 2,
      y: top,
      width: index === points.length - 1 ? width - right - x(index) + (index ? (x(index) - x(index - 1)) / 2 : 24) : (x(index + 1) - x(index - 1 >= 0 ? index - 1 : index)) / 2,
      height: height - top - bottom,
      tabindex: 0,
      role: "img",
      "aria-label": `${point.contest.title}，${detail}`,
    });
    const show = () => {
      focus.setAttribute("x1", x(index)); focus.setAttribute("x2", x(index)); focus.setAttribute("visibility", "visible");
      tooltip.hidden = false;
      if (participation) {
        tooltip.replaceChildren(
          node("span", { text: `${point.contest.title} #${participation.contestRank}，` }),
          ratingNode(participation.before),
          document.createTextNode(" → "),
          ratingNode(participation.after),
          document.createTextNode(" "),
          deltaNode(participation.delta),
        );
      } else {
        tooltip.textContent = `${point.contest.title} · 未参赛`;
      }
      tooltip.style.left = `${Math.min(78, Math.max(4, x(index) / width * 100))}%`;
      tooltip.style.top = `${Math.max(4, y(point.rating) / height * 100 - 12)}%`;
    };
    const hide = () => { focus.setAttribute("visibility", "hidden"); tooltip.hidden = true; };
    hit.addEventListener("mouseenter", show); hit.addEventListener("focus", show);
    hit.addEventListener("mouseleave", hide); hit.addEventListener("blur", hide);
    svg.append(hit);
    if (index === 0 || index === points.length - 1 || index % 3 === 0) {
      const label = svgNode("text", { class: "chart-axis", x: x(index), y: height - bottom + 22, "text-anchor": "middle" });
      label.textContent = String(point.contestIndex + 1); svg.append(label);
    }
  });
  wrap.append(svg, tooltip);
  figure.append(wrap, node("figcaption", { className: "chart-note", text: "横轴为系列比赛序号；实际参赛显示圆点，未参赛区间延续当时 Rating。悬停或聚焦查看详情。" }));
  return figure;
}

function participationTable(competitor) {
  const head = node("tr");
  ["比赛", "比赛排名", "赛前", "赛后", "变化"].forEach((label) => head.append(node("th", { scope: "col", text: label })));
  const body = node("tbody");
  competitor.participations.forEach((participation) => {
    const contest = state.series.contests[participation.contestIndex];
    const contestButton = node("button", { className: "link-button", type: "button", text: contest.title });
    contestButton.addEventListener("click", () => openContest(contest.id));
    const row = node("tr");
    row.append(node("td", {}, [contestButton]));
    row.append(node("td", { text: String(participation.contestRank) }));
    row.append(node("td", {}, [ratingNode(participation.before)]));
    row.append(node("td", {}, [ratingNode(participation.after)]));
    row.append(node("td", { className: participation.delta > 0 ? "positive" : participation.delta < 0 ? "negative" : "", text: formatDelta(participation.delta) }));
    body.append(row);
  });
  return node("div", { className: "compact-table-wrap", tabIndex: 0 }, [node("table", { className: "data-table compact-table" }, [node("thead", {}, [head]), body])]);
}

function openCompetitor(competitorId, updateUrl = true) {
  const competitor = state.index.competitorById.get(competitorId);
  if (!competitor) return showSeries();
  state.competitorId = competitor.id;
  state.contestId = "";
  if (updateUrl) setUrl("push");
  elements.seriesView.hidden = true;
  elements.detailView.hidden = false;
  const heading = node("div", { className: "detail-header" }, [
    node("div", {}, [
      node("p", { className: "eyebrow", text: "COMPETITOR" }),
      node("h2", { id: "detail-title", text: competitor.member, tabIndex: -1 }),
      node("p", { className: "detail-meta" }, [
        node("span", { text: competitor.school }), node("span", { text: `系列排名 #${competitor.rank}` }),
        node("span", {}, [document.createTextNode("最终 "), ratingNode(competitor.finalRating)]),
        node("span", { text: `${competitor.contestsParticipated} 次参赛` }),
      ]),
    ]), backButton(),
  ]);
  const chartPanel = node("section", { className: "panel", "aria-labelledby": "curve-heading" }, [node("h3", { id: "curve-heading", text: "Rating 曲线" }), ratingChart(competitor)]);
  const tablePanel = node("section", { className: "panel", "aria-labelledby": "participation-heading" }, [node("h3", { id: "participation-heading", text: "参赛记录" }), participationTable(competitor)]);
  elements.detailView.replaceChildren(heading, node("div", { className: "detail-grid" }, [chartPanel, tablePanel]));
  heading.querySelector("h2").focus();
}

async function loadSeries(seriesId, queryState = {}) {
  elements.status.hidden = false;
  elements.status.textContent = "正在加载数据…";
  elements.seriesView.hidden = true;
  elements.detailView.hidden = true;
  const loaded = await store.getSeries(seriesId);
  state.seriesId = loaded.series.id;
  state.series = loaded.series;
  state.index = loaded.index;
  elements.seriesSelect.value = state.seriesId;
  state.query = queryState.query ?? state.query;
  elements.searchInput.value = state.query;
  elements.status.hidden = true;
  if (queryState.competitor && state.index.competitorById.has(queryState.competitor)) openCompetitor(queryState.competitor, false);
  else if (queryState.contest && state.series.contests.some((contest) => contest.id === queryState.contest)) openContest(queryState.contest, false);
  else showSeries();
  setUrl();
}

async function initialize() {
  const index = await store.getIndex();
  const query = readQueryState(location.href);
  for (const entry of index.series) elements.seriesSelect.append(node("option", { value: entry.id, text: entry.title }));
  const seriesId = index.series.some((entry) => entry.id === query.series) ? query.series : index.defaultSeriesId;
  await loadSeries(seriesId, query);
}

elements.seriesSelect.addEventListener("change", () => loadSeries(elements.seriesSelect.value).catch(showError));
elements.searchInput.addEventListener("input", () => applySearch());
elements.seriesScroll.addEventListener("scroll", scheduleSeriesRows, { passive: true });
window.addEventListener("resize", scheduleSeriesRows);
window.addEventListener("popstate", () => {
  const query = readQueryState(location.href);
  if (query.series && query.series !== state.seriesId) loadSeries(query.series, query).catch(showError);
  else {
    state.query = query.query;
    elements.searchInput.value = query.query;
    if (query.competitor) openCompetitor(query.competitor, false);
    else if (query.contest) openContest(query.contest, false);
    else showSeries();
  }
});

initialize().catch(showError);
