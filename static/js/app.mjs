import {
  carriedRatings,
  createDataStore,
  formatDelta,
  listSchools,
  ratingTier,
  ratingTimeline,
  readQueryState,
  searchCompetitors,
  writeQueryState,
} from "./data.mjs?v=20260906-41";
import {
  buildDifficultyCurves,
  createProblemRatingStore,
  flattenProblemRatings,
  monotoneCubicPath,
  problemCurveColor,
  problemSeriesHasNames,
  readProblemRatingQuery,
  sortProblemRows,
  writeProblemRatingQuery,
} from "./problem-rating.mjs?v=20260906-41";
import {
  achievementDisplayParts,
  buildPreviewPower,
  buildPreviewRanks,
  buildPreviewSchoolRanks,
  bestAchievementMedal,
  createPreviewStore,
  listPreviewSchools,
  readPreviewQuery,
  searchPreviewTeams,
  sortPreviewTeams,
  writePreviewQuery,
} from "./preview.mjs?v=20260906-41";

import {
  createReviewStore, buildReviewAnalysis, selectReviewRows, readReviewQuery, writeReviewQuery,
} from "./review.mjs?v=20260906-41";

const ROW_HEIGHT = 44;
const OVERSCAN = 8;
const INDEX_URL = new URL("../data/index.json", import.meta.url).href;
const PROBLEM_RATING_INDEX_URL = new URL("../data/problem-rating/index.json", import.meta.url).href;
const store = createDataStore(INDEX_URL);
const problemRatingStore = createProblemRatingStore(PROBLEM_RATING_INDEX_URL);
const previewStore = createPreviewStore(INDEX_URL);
const reviewStore = createReviewStore(INDEX_URL);
const elements = {
  seriesList: document.querySelector("#series-list"),
  seriesModeSwitch: document.querySelector("#series-mode-switch"),
  participantRatingTab: document.querySelector("#participant-rating-tab"),
  problemRatingTab: document.querySelector("#problem-rating-tab"),
  previewTab: document.querySelector("#preview-tab"),
  reviewTab: document.querySelector("#review-tab"),
  reviewView: document.querySelector("#review-view"),
  reviewTitle: document.querySelector("#review-title"),
  reviewContestSelect: document.querySelector("#review-contest-select"),
  reviewMetrics: document.querySelector("#review-metrics"),
  reviewAgreement: document.querySelector("#review-agreement"),
  reviewCoverage: document.querySelector("#review-coverage"),
  reviewSources: document.querySelector("#review-sources"),
  reviewEmpty: document.querySelector("#review-empty"),
  reviewScroll: document.querySelector("#review-scroll"),
  reviewHead: document.querySelector("#review-head"),
  reviewBody: document.querySelector("#review-body"),
  participantControls: document.querySelector("#participant-controls"),
  searchLabelText: document.querySelector("#search-label-text"),
  searchInput: document.querySelector("#search-input"),
  clearSearchButton: document.querySelector("#clear-search-button"),
  schoolTags: document.querySelector("#school-tags"),
  schoolFilter: document.querySelector(".school-filter"),
  schoolFilterButton: document.querySelector("#school-filter-button"),
  schoolFilterMenu: document.querySelector("#school-filter-menu"),
  schoolFilterSearch: document.querySelector("#school-filter-search"),
  schoolOptions: document.querySelector("#school-options"),
  resultCount: document.querySelector("#result-count"),
  status: document.querySelector("#status"),
  seriesView: document.querySelector("#series-view"),
  seriesTitle: document.querySelector("#series-title"),
  seriesSummary: document.querySelector("#series-summary"),
  seriesHead: document.querySelector("#series-head"),
  seriesBody: document.querySelector("#series-body"),
  seriesScroll: document.querySelector("#series-scroll"),
  problemRatingView: document.querySelector("#problem-rating-view"),
  problemRatingTitle: document.querySelector("#problem-rating-title"),
  problemRatingSummary: document.querySelector("#problem-rating-summary"),
  problemResultCount: document.querySelector("#problem-result-count"),
  problemChart: document.querySelector("#problem-chart"),
  problemTableBody: document.querySelector("#problem-table-body"),
  problemNameCol: document.querySelector("#problem-name-col"),
  problemNameColumn: document.querySelector("#problem-name-column"),
  problemContestColumn: document.querySelector("#problem-contest-column"),
  problemContestSort: document.querySelector("#problem-contest-sort"),
  problemContestSortIndicator: document.querySelector("#problem-contest-sort-indicator"),
  problemRatingColumn: document.querySelector("#problem-rating-column"),
  problemRatingSort: document.querySelector("#problem-rating-sort"),
  problemRatingSortIndicator: document.querySelector("#problem-rating-sort-indicator"),
  previewView: document.querySelector("#preview-view"),
  previewTitle: document.querySelector("#preview-title"),
  previewContestSelect: document.querySelector("#preview-contest-select"),
  previewTeamSource: document.querySelector("#preview-team-source"),
  previewMetricSources: document.querySelector("#preview-metric-sources"),
  previewScroll: document.querySelector("#preview-scroll"),
  previewHead: document.querySelector("#preview-head"),
  previewBody: document.querySelector("#preview-body"),
  detailView: document.querySelector("#detail-view"),
  errorTemplate: document.querySelector("#error-template"),
};

const state = {
  seriesId: "",
  seriesEntry: null,
  view: "participants",
  query: "",
  schools: [],
  availableSchools: [],
  contestId: "",
  competitorId: "",
  series: null,
  index: null,
  siteIndex: null,
  filtered: [],
  renderFrame: 0,
  problemAvailableSeries: new Set(),
  problemSeries: null,
  problemSelectedContestIds: new Set(),
  problemSort: "contest",
  problemOrder: "asc",
  problemChartFrame: 0,
  previews: [],
  review: null,
  reviewContest: null,
  reviewAnalysis: null,
  reviewMetric: "power",
  reviewSort: "actualRank",
  reviewOrder: "asc",
  reviewRenderFrame: 0,
  preview: null,
  previewPower: new Map(),
  previewRanks: new Map(),
  previewSchoolRanks: new Map(),
  previewSort: "power",
  previewOrder: "desc",
  previewRenderFrame: 0,
};
let activePreviewTooltip = null;
let seriesLoadVersion = 0;

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
    className: deltaClass(delta),
    text: `(${formatDelta(delta)})`,
  });
}

function deltaClass(delta) {
  return delta > 0 ? "positive" : delta < 0 ? "negative" : "delta-zero";
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
  let url = writeQueryState(location.href, {
    series: state.seriesId,
    query: state.query,
    schools: state.schools,
    contest: state.contestId,
    competitor: state.competitorId,
  });
  url = writeProblemRatingQuery(url, {
    view: state.view,
    allContestIds: state.problemSeries?.contests.map(({ id }) => id) ?? [],
    selectedContestIds: state.problemSeries
      ? state.problemSeries.contests
        .filter(({ id }) => state.problemSelectedContestIds.has(id))
        .map(({ id }) => id)
      : [],
    sort: state.problemSort,
    order: state.problemOrder,
  });
  url = writePreviewQuery(url, {
    view: state.view,
    sort: state.previewSort,
    order: state.previewOrder,
    contest: state.preview?.id,
  });
  url = writeReviewQuery(url, {
    view: state.view, contest: state.reviewContest?.id, metric: state.reviewMetric,
    sort: state.reviewSort, order: state.reviewOrder,
  });
  history[mode === "push" ? "pushState" : "replaceState"](null, "", `${url.pathname}${url.search}${url.hash}`);
}

function showError(error) {
  console.error(error);
  elements.status.hidden = true;
  elements.seriesView.hidden = true;
  elements.problemRatingView.hidden = true;
  elements.previewView.hidden = true;
  elements.reviewView.hidden = true;
  elements.participantControls.hidden = true;
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

function personButton(competitor, rank) {
  const children = [node("span", { text: competitor.member })];
  children.push(node("small", {
    className: `person-context${competitor.school ? "" : " person-context-rank-only"}`,
  }, [
    node("span", { className: "mobile-rank", text: `#${rank}` }),
    ...(competitor.school ? [node("span", { className: "person-school", text: competitor.school })] : []),
  ]));
  const button = node("button", { className: "link-button person", type: "button" }, children);
  button.addEventListener("click", () => openCompetitor(competitor.id));
  return button;
}

function renderSeriesRows() {
  if (!state.series || state.view !== "participants" || elements.seriesView.hidden) return;
  const columns = state.series.contests.length * 2 + 4;
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
      row.append(node("td", {}, [personButton(competitor, competitor.rank)]));
      row.append(node("td", {}, [ratingNode(competitor.finalRating)]));
      row.append(node("td", { text: String(competitor.contestsParticipated) }));
      const participationByContest = new Map(competitor.participations.map((item) => [item.contestIndex, item]));
      const ratings = carriedRatings(competitor, state.series.contests.length, state.series.initialRating);
      ratings.forEach((rating, contestIndex) => {
        const contest = state.series.contests[contestIndex];
        const participation = participationByContest.get(contestIndex);
        const participationTitle = contest.rated === false
          ? `已参赛，本场 Unrated（${contest.unratedReason}），Rating 不变`
          : `已参赛，变化 ${formatDelta(participation?.delta ?? 0)}`;
        const ratingCell = node("td", {
          className: participation ? "rating-participated" : "rating-absent",
          title: participation ? participationTitle : "本场未参加，Rating 沿用",
        }, [ratingNode(rating)]);
        const deltaCell = node("td", {
          className: participation ? "rating-participated rating-delta" : "rating-absent rating-delta",
          title: participation ? participationTitle : "本场未参加",
        }, participation ? [deltaNode(participation.delta)] : []);
        row.append(ratingCell, deltaCell);
      });
      return row;
    },
  });
  elements.seriesBody.closest("table").setAttribute("aria-rowcount", String(state.filtered.length + 1));
}

function renderSeriesHeader() {
  const contestRow = node("tr");
  ["排名", "参赛者 / 学校", "最终 Rating", "参赛"].forEach((label) => contestRow.append(node("th", { scope: "col", text: label })));
  state.series.contests.forEach((contest) => {
    const label = contest.rated === false ? `${contest.title}（Unrated）` : contest.title;
    const title = contest.rated === false ? `${contest.title} · Unrated：${contest.unratedReason}` : contest.title;
    const button = node("button", { type: "button", className: "contest-button", text: label, title });
    button.addEventListener("click", () => openContest(contest.id));
    contestRow.append(node("th", { className: "contest-heading", scope: "colgroup", colSpan: 2 }, [button]));
  });
  elements.seriesHead.replaceChildren(contestRow);
  const table = elements.seriesHead.closest("table");
  table.querySelector("colgroup")?.remove();
  table.prepend(columnGroup([62, 220, 104, 76, ...state.series.contests.flatMap(() => [72, 80])]));
  table.style.setProperty("--series-contest-width", `${state.series.contests.length * 152}px`);
}

function renderSchoolTags() {
  const fragment = document.createDocumentFragment();
  for (const school of state.schools) {
    const remove = node("button", {
      className: "school-tag-remove",
      type: "button",
      text: "×",
      title: `移除 ${school}`,
      "aria-label": `移除学校筛选：${school}`,
    });
    remove.addEventListener("click", () => {
      state.schools = state.schools.filter((item) => item !== school);
      renderSchoolControls();
      applySearch();
      elements.searchInput.focus();
    });
    fragment.append(node("span", { className: "school-tag" }, [
      node("span", { text: school }),
      remove,
    ]));
  }
  elements.schoolTags.replaceChildren(fragment);
}

function renderSchoolOptions() {
  const query = elements.schoolFilterSearch.value.trim().toLocaleLowerCase();
  const schools = state.availableSchools.filter((school) => school.toLocaleLowerCase().includes(query));
  const fragment = document.createDocumentFragment();
  for (const school of schools) {
    const selected = state.schools.includes(school);
    const option = node("button", {
      className: "school-option",
      type: "button",
      role: "option",
      "aria-selected": String(selected),
    }, [
      node("span", { text: school }),
      node("span", { className: "school-option-mark", text: selected ? "✓" : "" }),
    ]);
    option.dataset.school = school;
    option.addEventListener("click", () => {
      state.schools = selected
        ? state.schools.filter((item) => item !== school)
        : [...state.schools, school];
      renderSchoolControls();
      applySearch();
      [...elements.schoolOptions.querySelectorAll(".school-option")]
        .find((item) => item.dataset.school === school)?.focus();
    });
    fragment.append(option);
  }
  if (!schools.length) fragment.append(node("p", { className: "school-options-empty", text: "没有匹配的学校" }));
  elements.schoolOptions.replaceChildren(fragment);
}

function renderSchoolControls() {
  renderSchoolTags();
  renderSchoolOptions();
  elements.schoolFilterButton.textContent = state.schools.length
    ? `已选 ${state.schools.length} 所学校`
    : "选择学校";
  elements.clearSearchButton.disabled = !elements.searchInput.value
    && !state.schools.length;
}

function setSchoolMenu(open) {
  elements.schoolFilterMenu.hidden = !open;
  elements.schoolFilterButton.setAttribute("aria-expanded", String(open));
  if (open) {
    elements.schoolFilterSearch.value = "";
    renderSchoolOptions();
    elements.schoolFilterSearch.focus();
  }
}

function applySearch({ resetScroll = true, updateUrl = true } = {}) {
  state.query = elements.searchInput.value;
  if (state.view === "review") {
    state.filtered = selectReviewRows(state.reviewAnalysis, {
      sort: state.reviewSort, order: state.reviewOrder, query: state.query, schools: state.schools,
    });
    elements.resultCount.textContent = `${state.filtered.length.toLocaleString("zh-CN")} 支队伍`;
    elements.clearSearchButton.disabled = !state.query && !state.schools.length;
    elements.reviewEmpty.hidden = Boolean(state.filtered.length);
    elements.reviewEmpty.textContent = state.reviewAnalysis.rows.length ? "没有符合搜索条件的队伍。" : "没有实际参赛且当前指标有效的队伍。";
    if (resetScroll) elements.reviewScroll.scrollTop = 0;
    else {
      const maximum = Math.max(0, state.filtered.length * ROW_HEIGHT
        + elements.reviewHead.offsetHeight - elements.reviewScroll.clientHeight);
      elements.reviewScroll.scrollTop = Math.min(elements.reviewScroll.scrollTop, maximum);
    }
    scheduleReviewRows();
    if (updateUrl) setUrl();
    return;
  }
  if (state.view === "preview") {
    const sortedTeams = sortPreviewTeams(
      state.preview.teams,
      state.previewSort,
      state.previewOrder,
      state.previewPower,
    );
    state.previewSchoolRanks = buildPreviewSchoolRanks(
      sortedTeams,
      state.previewSort,
      state.previewPower,
    );
    state.filtered = searchPreviewTeams(
      sortedTeams,
      state.query,
      state.schools,
    );
    elements.resultCount.textContent = `${state.filtered.length.toLocaleString("zh-CN")} 支队伍`;
  } else {
    state.filtered = searchCompetitors(state.series.competitors, state.query, state.schools);
    elements.resultCount.textContent = `${state.filtered.length.toLocaleString("zh-CN")} 位参赛者`;
  }
  elements.clearSearchButton.disabled = !state.query
    && !state.schools.length;
  if (state.view === "preview") {
    if (resetScroll) elements.previewScroll.scrollTop = 0;
    schedulePreviewRows();
  } else {
    if (resetScroll) elements.seriesScroll.scrollTop = 0;
    scheduleSeriesRows();
  }
  if (updateUrl) setUrl();
}

function updateSeriesMode() {
  const participantsSupported = Boolean(state.seriesEntry?.path);
  const problemSupported = participantsSupported && state.problemAvailableSeries.has(state.seriesId);
  const previewSupported = Boolean(state.previews.length);
  const reviewSupported = Boolean(state.seriesEntry?.reviewPath);
  const supportedCount = [participantsSupported, problemSupported, previewSupported, reviewSupported].filter(Boolean).length;
  elements.seriesModeSwitch.hidden = supportedCount === 0;
  elements.participantRatingTab.hidden = !participantsSupported;
  elements.problemRatingTab.hidden = !problemSupported;
  elements.previewTab.hidden = !previewSupported;
  elements.reviewTab.hidden = !reviewSupported;
  elements.reviewTab.setAttribute("aria-selected", String(state.view === "review"));
  elements.participantRatingTab.setAttribute(
    "aria-selected",
    String(state.view === "participants"),
  );
  elements.problemRatingTab.setAttribute(
    "aria-selected",
    String(state.view === "problem-rating"),
  );
  elements.previewTab.setAttribute("aria-selected", String(state.view === "preview"));
}

function showSeries() {
  if (!state.series) return showPreview();
  state.view = "participants";
  state.contestId = "";
  state.competitorId = "";
  elements.participantControls.hidden = false;
  elements.detailView.hidden = true;
  elements.problemRatingView.hidden = true;
  elements.previewView.hidden = true;
  elements.reviewView.hidden = true;
  elements.seriesView.hidden = false;
  state.availableSchools = listSchools(state.series.competitors);
  state.schools = state.schools.filter((school) => state.availableSchools.includes(school));
  elements.searchLabelText.textContent = "搜索参赛者或学校";
  elements.searchInput.placeholder = "输入参赛者名称或学校";
  renderSchoolControls();
  updateSeriesMode();
  elements.seriesTitle.textContent = state.series.title;
  elements.seriesSummary.textContent = `${state.series.contests.length} 场比赛 · ${state.series.competitors.length.toLocaleString("zh-CN")} 位参赛者`;
  renderSeriesHeader();
  applySearch({ resetScroll: false });
}

function formatPreviewRating(value, minimumFractionDigits = 0) {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("zh-CN", {
    useGrouping: false,
    minimumFractionDigits,
    maximumFractionDigits: 2,
  }).format(value);
}

function previewRatingNode(sourceId, value) {
  if (value === null || value === undefined) {
    return node("span", { className: "preview-rating preview-missing", text: "—" });
  }
  if (sourceId === "previousSeason") {
    return ratingNode(value, "preview-rating preview-rating-previous-season");
  }
  if (sourceId === "xcpcElo") {
    if (value >= 3000) {
      const text = formatPreviewRating(value);
      return node("span", {
        className: "preview-rating preview-rating-xcpc-elo preview-rating-xcpc-elo-legendary",
      }, [
        node("span", { className: "preview-rating-xcpc-elo-first", text: text[0] }),
        document.createTextNode(text.slice(1)),
      ]);
    }
    const ratingElement = ratingNode(value, "preview-rating preview-rating-xcpc-elo");
    if (value >= 2300 && value < 2400) {
      ratingElement.classList.remove("rating-orange");
      ratingElement.classList.add("rating-red");
    }
    return ratingElement;
  }
  return node("span", {
    className: `preview-rating preview-rating-${sourceId}`,
    text: formatPreviewRating(value, ["xcpcrating", "cpcfinder"].includes(sourceId) ? 2 : 0),
  });
}

function previewRankedValue(displayed, rank) {
  if (rank === null) return displayed;
  return node("span", { className: "preview-ranked-value" }, [
    displayed,
    node("small", { className: "preview-global-rank", text: `#${rank}` }),
  ]);
}

function previewValueControl(team, value, rank, memberValue, renderValue) {
  const tooltip = node("span", { className: "preview-member-tooltip", role: "tooltip" });
  for (const member of team.members) {
    tooltip.append(node("span", {}, [
      node("strong", { text: member.name }),
      renderValue(memberValue(member)),
    ]));
  }
  const displayed = renderValue(value);
  const rankLabel = rank === null ? "" : `；全体队伍第 ${rank} 名`;
  const control = node("span", {
    className: "preview-value-control",
    tabIndex: 0,
    "aria-label": `${displayed.textContent}${rankLabel}；悬浮或聚焦查看所有成员明细`,
  }, [previewRankedValue(displayed, rank), tooltip]);
  attachPreviewTooltip(control, tooltip);
  return control;
}

function positionPreviewTooltip(control, tooltip) {
  const viewportMargin = 8;
  const gap = 6;
  const controlRect = control.getBoundingClientRect();
  const tooltipRect = tooltip.getBoundingClientRect();
  const maximumLeft = Math.max(viewportMargin, window.innerWidth - tooltipRect.width - viewportMargin);
  const left = Math.min(Math.max(viewportMargin, controlRect.right - tooltipRect.width), maximumLeft);
  const below = controlRect.bottom + gap;
  const above = controlRect.top - tooltipRect.height - gap;
  const top = below + tooltipRect.height <= window.innerHeight - viewportMargin
    ? below
    : Math.max(viewportMargin, above);
  tooltip.style.left = `${Math.round(left)}px`;
  tooltip.style.top = `${Math.round(top)}px`;
}

function attachPreviewTooltip(control, tooltip) {
  let hovering = false;
  let focused = false;
  const show = () => {
    if (activePreviewTooltip && activePreviewTooltip !== tooltip) {
      activePreviewTooltip.classList.remove("preview-tooltip-visible");
      activePreviewTooltip.remove();
    }
    document.body.append(tooltip);
    positionPreviewTooltip(control, tooltip);
    tooltip.classList.add("preview-tooltip-visible");
    activePreviewTooltip = tooltip;
  };
  const hide = () => {
    if (hovering || focused) return;
    tooltip.classList.remove("preview-tooltip-visible");
    tooltip.remove();
    if (activePreviewTooltip === tooltip) activePreviewTooltip = null;
  };
  control.addEventListener("mouseenter", () => {
    hovering = true;
    show();
  });
  control.addEventListener("mouseleave", () => {
    hovering = false;
    hide();
  });
  control.addEventListener("focus", () => {
    focused = true;
    show();
  });
  control.addEventListener("blur", () => {
    focused = false;
    hide();
  });
}

function previewMedalNode(medals) {
  const display = node("span", {
    className: "medal-values",
    "aria-label": `金牌 ${medals.gold}，银牌 ${medals.silver}，铜牌 ${medals.bronze}`,
  });
  for (const [medal, icon] of [["gold", "🥇"], ["silver", "🥈"], ["bronze", "🥉"]]) {
    display.append(
      node("span", { className: "medal-icon", text: icon, "aria-hidden": "true" }),
      node("span", { className: "medal-count", text: String(medals[medal]), "aria-hidden": "true" }),
    );
  }
  return display;
}

function achievementLabel(achievement) {
  return achievementDisplayParts(achievement).join(" · ");
}

function achievementRow(achievement) {
  const parts = achievementDisplayParts(achievement);
  return node("span", { className: "preview-achievement-row" }, [
    node("span", { className: "preview-achievement-competition", text: parts[0] }),
    node("span", { className: "preview-achievement-separator", text: "·" }),
    node("span", { className: "preview-achievement-result", text: parts[1] }),
    node("span", { className: "preview-achievement-separator", text: "·" }),
    node("span", { className: "preview-achievement-score", text: parts[2] }),
  ]);
}

function previewMemberControl(member) {
  const noiMedal = bestAchievementMedal(member.achievements, "noi");
  const ioiMedal = bestAchievementMedal(member.achievements, "ioi");
  const classes = [
    "preview-member-name",
    noiMedal ? `has-noi noi-${noiMedal}` : "",
    ioiMedal ? `has-ioi ioi-${ioiMedal}` : "",
  ].filter(Boolean).join(" ");
  const name = node("span", { className: classes, text: member.name });
  if (!member.achievements.length) return name;

  const tooltip = node("span", {
    className: "preview-member-tooltip preview-achievement-tooltip",
    role: "tooltip",
  }, [
    node("strong", { text: member.name }),
    node("span", { className: "preview-achievement-list" }, [
      ...member.achievements.map(achievementRow),
    ]),
  ]);
  const control = node("span", {
    className: "preview-member-control",
    tabIndex: 0,
    "aria-label": `${member.name}；${member.achievements.map(achievementLabel).join("；")}`,
  }, [name, tooltip]);
  attachPreviewTooltip(control, tooltip);
  return control;
}

function radarPoint(index, count, dimensionCount, maximum, radius, centerX, centerY) {
  const angle = -Math.PI / 2 + index * Math.PI * 2 / dimensionCount;
  const distance = radius * count / maximum;
  return [centerX + Math.cos(angle) * distance, centerY + Math.sin(angle) * distance];
}

function radarPoints(counts, maximum, radius, centerX, centerY) {
  return counts.map((count, index) => (
    radarPoint(index, count, counts.length, maximum, radius, centerX, centerY).join(",")
  )).join(" ");
}

function previewPowerRadar(power) {
  const labels = [...state.preview.metricSources.map(({ title }) => title), "奖牌"];
  const maximum = Math.max(1, state.preview.teams.length - 1);
  const centerX = 150;
  const centerY = 105;
  const radius = 58;
  const labelRadius = 87;
  const svg = svgNode("svg", {
    class: "preview-power-radar",
    viewBox: "0 0 300 215",
    role: "img",
    "aria-label": `五维综合战力雷达图，超过队伍数：${power.counts.join("、")}`,
  });
  for (const scale of [0.5, 1]) {
    svg.append(svgNode("polygon", {
      class: "preview-power-grid",
      points: radarPoints(labels.map(() => maximum * scale), maximum, radius, centerX, centerY),
    }));
  }
  labels.forEach((label, index) => {
    const outer = radarPoint(index, maximum, labels.length, maximum, radius, centerX, centerY);
    const labelPoint = radarPoint(
      index,
      maximum,
      labels.length,
      maximum,
      labelRadius,
      centerX,
      centerY,
    );
    svg.append(svgNode("line", {
      class: "preview-power-axis",
      x1: centerX,
      y1: centerY,
      x2: outer[0],
      y2: outer[1],
    }));
    const text = svgNode("text", {
      class: "preview-power-label",
      x: labelPoint[0],
      y: labelPoint[1],
      "text-anchor": labelPoint[0] < centerX - 8
        ? "end"
        : labelPoint[0] > centerX + 8 ? "start" : "middle",
    });
    text.textContent = label;
    svg.append(text);
  });
  svg.append(svgNode("polygon", {
    class: "preview-power-shape",
    points: radarPoints(power.counts, maximum, radius, centerX, centerY),
  }));
  return svg;
}

function previewPowerControl(team) {
  const power = state.previewPower.get(team.id);
  const tooltip = node("span", { className: "preview-power-tooltip", role: "tooltip" }, [
    node("strong", { text: `综合战力 #${power.rank}` }),
    previewPowerRadar(power),
  ]);
  const control = node("span", {
    className: "preview-power-control",
    tabIndex: 0,
    "aria-label": `综合战力第 ${power.rank} 名；悬浮或聚焦查看五维雷达图`,
  }, [document.createTextNode(`#${power.rank}`), tooltip]);
  attachPreviewTooltip(control, tooltip);
  return control;
}

function renderPreviewRows() {
  if (!state.preview || state.view !== "preview") return;
  if (activePreviewTooltip) {
    activePreviewTooltip.classList.remove("preview-tooltip-visible");
    activePreviewTooltip.remove();
    activePreviewTooltip = null;
  }
  const columns = state.preview.metricSources.length + 5;
  renderVirtualRows({
    container: elements.previewScroll,
    body: elements.previewBody,
    items: state.filtered,
    columns,
    createRow(team, index) {
      const row = node("tr");
      row.dataset.teamId = team.id;
      row.setAttribute("aria-rowindex", String(index + 2));
      const schoolRank = state.previewSchoolRanks.get(team.id);
      row.append(node("td", { className: "preview-school-cell", title: team.school }, [
        node("span", { className: "preview-school-content" }, [
          node("small", { className: "preview-school-rank", text: schoolRank ? `#${schoolRank}` : "" }),
          node("span", { text: team.school }),
        ]),
      ]));
      const memberNames = team.members.map(({ name }) => name).join(" / ");
      const identityTooltip = node("span", { className: "preview-member-tooltip", role: "tooltip" }, [
        node("strong", { text: "成员" }),
        ...team.members.map(({ name }) => node("span", {}, [node("strong", { text: name })])),
      ]);
      const identityControl = node("span", {
        className: "preview-team-identity",
        tabIndex: 0,
        "aria-label": `${team.name}，${team.school}，成员：${memberNames}`,
      }, [
        node("span", { className: "identity-primary", text: team.name }),
        node("small", {
          className: "identity-secondary",
          text: `${schoolRank ? `#${schoolRank} ` : ""}${team.school}`,
        }),
        identityTooltip,
      ]);
      attachPreviewTooltip(identityControl, identityTooltip);
      row.append(node("td", { className: "preview-team-cell", title: team.name }, [identityControl]));
      const memberChildren = [];
      team.members.forEach((member, memberIndex) => {
        if (memberIndex) memberChildren.push(document.createTextNode(" / "));
        memberChildren.push(previewMemberControl(member));
      });
      row.append(node("td", {
        className: "preview-members-cell",
        title: memberNames,
      }, memberChildren));
      row.append(node("td", { className: "preview-metric-cell preview-power-cell" }, [
        previewPowerControl(team),
      ]));
      for (const source of state.preview.metricSources) {
        const value = team.ratings[source.id];
        const rank = state.previewRanks.get(team.id).ratings[source.id];
        row.append(node("td", {
          className: `preview-metric-cell${value === null ? " preview-missing" : ""}`,
        }, [previewValueControl(
          team,
          value,
          rank,
          (member) => member.ratings[source.id],
          (rating) => previewRatingNode(source.id, rating),
        )]));
      }
      row.append(node("td", { className: "preview-metric-cell preview-medals" }, [
        previewValueControl(
          team,
          team.medals,
          state.previewRanks.get(team.id).medals,
          (member) => member.medals,
          previewMedalNode,
        ),
      ]));
      return row;
    },
  });
  elements.previewBody.closest("table").setAttribute("aria-rowcount", String(state.filtered.length + 1));
}

function schedulePreviewRows() {
  cancelAnimationFrame(state.previewRenderFrame);
  state.previewRenderFrame = requestAnimationFrame(renderPreviewRows);
}

function setPreviewSort(sort) {
  const defaultOrder = ["school", "name", "members"].includes(sort) ? "asc" : "desc";
  state.previewOrder = state.previewSort === sort
    ? state.previewOrder === "asc" ? "desc" : "asc"
    : defaultOrder;
  state.previewSort = sort;
  renderPreviewHeader();
  applySearch();
}

function previewSortHeader(label, sort, mobileLabel = label) {
  const active = state.previewSort === sort;
  const indicator = active ? state.previewOrder === "asc" ? "↑" : "↓" : "";
  const heading = node("th", { scope: "col" }, [
    node("button", { className: "table-sort-button", type: "button", onclick: () => setPreviewSort(sort) }, [
      node("span", { className: "desktop-column-label", text: label }),
      node("span", { className: "mobile-column-label", text: mobileLabel }),
      node("span", { text: indicator, "aria-hidden": "true" }),
    ]),
  ]);
  if (active) heading.setAttribute("aria-sort", state.previewOrder === "asc" ? "ascending" : "descending");
  return heading;
}

function renderPreviewHeader() {
  const row = node("tr");
  row.append(
    previewSortHeader("学校", "school"),
    previewSortHeader("中文队名", "name", "队伍"),
    previewSortHeader("成员", "members"),
    previewSortHeader("综合战力", "power"),
  );
  for (const source of state.preview.metricSources) row.append(previewSortHeader(source.title, source.id));
  row.append(previewSortHeader("奖牌", "medals"));
  elements.previewHead.replaceChildren(row);
  const table = elements.previewHead.closest("table");
  const widths = [200, 170, 190, 96, ...state.preview.metricSources.map(() => 112), 150];
  table.style.setProperty("--preview-table-width", `${widths.reduce((sum, width) => sum + width, 0)}px`);
  table.style.setProperty("--preview-non-frozen-width", `${widths.slice(2).reduce((sum, width) => sum + width, 0)}px`);
  table.querySelector("colgroup")?.remove();
  table.prepend(columnGroup(widths));
}

function renderSourceLinks(container, label, sources) {
  const children = [node("strong", { text: label })];
  sources.forEach((source, index) => {
    children.push(document.createTextNode(index ? " · " : " "));
    children.push(node("a", {
      text: source.title,
      href: source.url,
      target: source.url.startsWith("http") ? "_blank" : "",
      rel: source.url.startsWith("http") ? "noopener noreferrer" : "",
    }));
  });
  container.replaceChildren(...children);
}

function renderPreviewSources() {
  renderSourceLinks(elements.previewTeamSource, "名单来源：", [state.preview.teamSource]);
  renderSourceLinks(elements.previewMetricSources, "数据来源：", state.preview.metricSources);
}

function showPreview(updateUrl = false) {
  if (!state.preview) return showSeries();
  state.view = "preview";
  state.contestId = "";
  state.competitorId = "";
  state.availableSchools = listPreviewSchools(state.preview.teams);
  state.schools = state.schools.filter((school) => state.availableSchools.includes(school));
  elements.searchLabelText.textContent = "搜索学校、队伍或成员";
  elements.searchInput.placeholder = "输入学校、中文队名或成员姓名";
  renderSchoolControls();
  elements.participantControls.hidden = false;
  elements.detailView.hidden = true;
  elements.seriesView.hidden = true;
  elements.problemRatingView.hidden = true;
  elements.previewView.hidden = false;
  elements.reviewView.hidden = true;
  updateSeriesMode();
  elements.previewTitle.textContent = state.preview.title;
  elements.previewContestSelect.replaceChildren(...state.previews.map(p => node("option", { value: p.id, text: p.title })));
  elements.previewContestSelect.value = state.preview.id;
  document.querySelector("#preview-time").textContent = state.preview.id === "icpc-2026-preliminary-1"
    ? "比赛时间：2026年9月6日 13:00-18:00"
    : `比赛时间：${new Intl.DateTimeFormat("zh-CN", { timeZone: "Asia/Shanghai", dateStyle: "long", timeStyle: "short" }).format(new Date(state.preview.sortAt))}`;
  renderPreviewSources();
  renderPreviewHeader();
  applySearch({ resetScroll: false, updateUrl: false });
  setUrl(updateUrl ? "push" : "replace");
}

function choosePreview(id) {
  state.preview = state.previews.find(p => p.id === id) ?? state.previews[0];
  const metrics = state.preview.metricSources.map(s => s.id);
  state.previewPower = buildPreviewPower(state.preview.teams, metrics);
  state.previewRanks = buildPreviewRanks(state.preview.teams, metrics);
}

function renderReviewHeader() {
  const metricTitle = state.reviewMetric === "power" ? "综合战力"
    : state.reviewMetric === "medals" ? "奖牌"
      : state.preview.metricSources.find(s => s.id === state.reviewMetric).title;
  const columns = [["学校", "school"], ["队伍", "name"], ["成员", "members"],
    [metricTitle, "metric"], ["前瞻排名", "previewRank"], ["实际排名", "actualRank"],
    ["名次变化", "change"], ["上涨程度", "growth"]];
  const row = node("tr");
  for (const [label, sort] of columns) {
    const active = state.reviewSort === sort;
    const isRank = sort === "previewRank" || sort === "actualRank";
    const heading = node("th", { scope: "col" });
    if (active) heading.setAttribute("aria-sort", state.reviewOrder === "asc" ? "ascending" : "descending");
    heading.append(node("button", {
      type: "button", className: `table-sort-button${isRank ? " review-rank-sort" : ""}`,
      onclick: () => {
        const order = active ? state.reviewOrder === "asc" ? "desc" : "asc"
          : ["change", "growth", "metric"].includes(sort) ? "desc" : "asc";
        state.reviewSort = sort;
        state.reviewOrder = order;
        renderReviewHeader();
        applySearch({ updateUrl: false });
        setUrl("push");
      },
    }, [
      node("span", { text: `${label}${active ? state.reviewOrder === "asc" ? " ↑" : " ↓" : ""}` }),
      ...(isRank ? [node("small", { className: "review-original-rank", text: "（过滤前）" })] : []),
    ]));
    row.append(heading);
  }
  elements.reviewHead.replaceChildren(row);
  const table = elements.reviewHead.closest("table");
  const widths = [200, 170, 190, 150, 110, 110, 110, 110];
  table.style.setProperty("--preview-table-width", `${widths.reduce((a, b) => a + b)}px`);
  table.style.setProperty("--preview-non-frozen-width", `${widths.slice(2).reduce((a, b) => a + b)}px`);
  table.querySelector("colgroup")?.remove();
  table.prepend(columnGroup(widths));
}

function renderReviewRows() {
  if (state.view !== "review" || !state.reviewAnalysis) return;
  // clientWidth excludes the vertical scrollbar; cqw can include its gutter.
  elements.reviewBody.closest("table").style.setProperty(
    "--review-column-extra", `${Math.max(0, (elements.reviewScroll.clientWidth - 1150) / 5)}px`,
  );
  if (activePreviewTooltip) {
    activePreviewTooltip.remove();
    activePreviewTooltip = null;
  }
  renderVirtualRows({
    container: elements.reviewScroll, body: elements.reviewBody, items: state.filtered, columns: 8,
    createRow: (team, index) => {
      const row = node("tr", { "aria-rowindex": String(index + 2) });
      row.dataset.teamId = team.id;
      row.append(node("td", { className: "preview-school-cell", text: team.school, title: team.school }));
      const memberNames = team.members.map(m => m.name).join(" / ");
      const tooltip = node("span", { className: "preview-member-tooltip", role: "tooltip" }, [
        node("strong", { text: "成员" }), node("span", { text: memberNames }),
      ]);
      const identity = node("span", {
        className: "preview-team-identity", tabIndex: 0,
        "aria-label": `${team.name}，${team.school}，成员：${memberNames}`,
      }, [node("span", { className: "identity-primary", text: team.name }),
        node("small", { className: "identity-secondary", text: team.school }), tooltip]);
      attachPreviewTooltip(identity, tooltip);
      row.append(node("td", { className: "preview-team-cell", title: team.name }, [identity]));
      row.append(node("td", { className: "preview-members-cell", text: memberNames, title: memberNames }));
      const metricValue = state.reviewMetric === "power"
        ? previewPowerControl(team)
        : state.reviewMetric === "medals"
          ? previewValueControl(team, team.medals, null, m => m.medals, previewMedalNode)
          : previewValueControl(team, team.ratings[state.reviewMetric], null,
            m => m.ratings[state.reviewMetric], value => previewRatingNode(state.reviewMetric, value));
      row.append(node("td", { className: "preview-metric-cell" }, [metricValue]));
      for (const [rank, original] of [[team.previewRank, team.originalPreviewRank], [team.actualRank, team.originalActualRank]]) {
        row.append(node("td", {}, [node("span", {
          className: "review-rank-pair", "aria-label": `筛选后第 ${rank} 名，过滤前第 ${original} 名`,
        }, [
          node("span", { text: `#${rank}` }),
          node("small", { className: "review-original-rank", text: `(#${original})`, title: `过滤前第 ${original} 名` }),
        ])]));
      }
      row.append(node("td", {}, [node("span", {
        className: `review-rank-change ${deltaClass(team.change)}`,
        "aria-label": team.change ? `${team.change > 0 ? "上涨" : "下降"} ${Math.abs(team.change)} 名` : "名次不变",
      }, [
        node("span", { className: "review-change-arrow", text: team.change > 0 ? "↑" : team.change < 0 ? "↓" : "", "aria-hidden": "true" }),
        node("span", { className: "review-change-number", text: team.change ? String(Math.abs(team.change)) : "—", "aria-hidden": "true" }),
      ])]));
      const growth = team.growth.toFixed(3);
      row.append(node("td", {}, [node("span", {
        className: deltaClass(team.change), text: `${team.growth > 0 ? "+" : ""}${growth}`,
      })]));
      return row;
    },
  });
  elements.reviewBody.closest("table").setAttribute("aria-rowcount", String(state.filtered.length + 1));
}

function scheduleReviewRows() {
  cancelAnimationFrame(state.reviewRenderFrame);
  state.reviewRenderFrame = requestAnimationFrame(renderReviewRows);
}

function renderReviewMetrics(metrics) {
  elements.reviewMetrics.replaceChildren(...metrics.map(metric => {
    const analysis = buildReviewAnalysis(state.preview, state.reviewContest, metric.id);
    const value = analysis.agreement.value;
    const selected = state.reviewMetric === metric.id;
    const coefficient = value === null ? "无法计算" : value.toFixed(3);
    const coverage = analysis.coverage === null ? "—" : `${(analysis.coverage * 100).toFixed(1)}%`;
    const bar = node("span", { className: "review-metric-bar", "aria-hidden": "true" }, [
      node("span", { className: value < 0 ? "review-metric-fill negative-fill" : "review-metric-fill" }),
    ]);
    bar.style.setProperty("--agreement-start", `${value < 0 ? 50 + value * 50 : 50}%`);
    bar.style.setProperty("--agreement-width", `${Math.abs(value ?? 0) * 50}%`);
    const button = node("button", {
      type: "button", className: "review-metric-card", "aria-pressed": String(selected),
      "aria-controls": "review-scroll", title: value === null ? analysis.agreement.reason : `${metric.title}：点击查看队伍排名对比`,
      onclick: () => {
        if (state.reviewMetric === metric.id) return;
        showReview({ reviewMetric: metric.id }, true).then(() => {
          [...elements.reviewMetrics.children].find(el => el.dataset.metric === metric.id)?.focus({ preventScroll: true });
        }).catch(showError);
      },
    }, [
      node("span", { className: "review-metric-title", text: metric.title }),
      node("strong", { className: "review-metric-coefficient", text: coefficient }),
      bar,
      node("small", { text: `${analysis.rows.length} 队 · 覆盖 ${coverage}` }),
    ]);
    button.dataset.metric = metric.id;
    return button;
  }));
}

async function showReview(query = {}, updateUrl = false) {
  const entry = state.seriesEntry;
  if (!entry.reviewPath) return showSeries();
  const updatingVisibleReview = state.view === "review" && !elements.reviewView.hidden && state.review;
  // Set the view before loading so navigation away cannot be overwritten by a late response.
  state.view = "review";
  updateSeriesMode();
  if (!updatingVisibleReview) {
    elements.status.hidden = false;
    elements.status.textContent = "正在加载复盘数据…";
    for (const view of [elements.seriesView, elements.previewView, elements.problemRatingView, elements.detailView, elements.reviewView]) view.hidden = true;
    elements.participantControls.hidden = true;
  }
  const review = state.review ?? await reviewStore.getSeries(entry, state.previews);
  if (state.seriesEntry !== entry || state.view !== "review") return;
  state.review = review;
  state.reviewContest = review.contests.find(c => c.id === query.reviewContest)
    ?? state.reviewContest ?? review.contests.at(-1);
  choosePreview(state.reviewContest.previewId);
  const metrics = [{ id: "power", title: "综合战力" }, ...state.preview.metricSources, { id: "medals", title: "奖牌" }];
  const requestedMetric = query.reviewMetric ?? state.reviewMetric;
  state.reviewMetric = metrics.some(m => m.id === requestedMetric) ? requestedMetric : "power";
  state.reviewSort = query.reviewSort ?? state.reviewSort;
  state.reviewOrder = query.reviewOrder ?? state.reviewOrder;
  state.reviewAnalysis = buildReviewAnalysis(state.preview, state.reviewContest, state.reviewMetric);
  state.contestId = "";
  state.competitorId = "";
  const activeTeamIds = new Set(state.reviewContest.teams.filter(t => t.hasActivity).map(t => t.previewTeamId));
  state.availableSchools = listPreviewSchools(state.preview.teams.filter(t => activeTeamIds.has(t.id)));
  state.schools = (query.schools ?? state.schools).filter(s => state.availableSchools.includes(s));
  state.query = query.query ?? state.query;
  elements.searchInput.value = state.query;
  elements.searchLabelText.textContent = "搜索学校、队伍或成员";
  elements.searchInput.placeholder = "输入学校、中文队名或成员姓名";
  renderSchoolControls();
  elements.reviewTitle.textContent = state.reviewContest.title;
  elements.reviewContestSelect.replaceChildren(...review.contests.map(c => node("option", { value: c.id, text: c.title })));
  elements.reviewContestSelect.value = state.reviewContest.id;
  renderReviewMetrics(metrics);
  const analysis = state.reviewAnalysis;
  const coefficient = analysis.agreement.value === null
    ? `无法计算（${analysis.agreement.reason}）` : analysis.agreement.value.toFixed(3);
  const metricTitle = metrics.find(m => m.id === state.reviewMetric).title;
  elements.reviewAgreement.replaceChildren(node("strong", { text: `当前指标：${metricTitle} · 符合度 ${coefficient}` }));
  elements.reviewCoverage.textContent = `有效队伍：${analysis.rows.length} / ${analysis.activeCount} 支实际参赛前瞻队伍 · 覆盖率：${analysis.coverage === null ? "—" : `${(analysis.coverage * 100).toFixed(1)}%`}`;
  renderSourceLinks(elements.reviewSources, "数据来源：", [state.reviewContest.source, ...state.preview.metricSources]);
  renderReviewHeader();
  elements.status.hidden = true;
  elements.participantControls.hidden = false;
  elements.reviewView.hidden = false;
  applySearch({ updateUrl: false, resetScroll: !updatingVisibleReview });
  setUrl(updateUrl ? "push" : "replace");
}

function backButton() {
  const button = node("button", { className: "back-button", type: "button", text: "返回系列" });
  button.addEventListener("click", openSeriesHome);
  return button;
}

function openSeriesHome() {
  if (state.view === "participants" && !state.contestId && !state.competitorId
      && !elements.seriesView.hidden) return;
  state.contestId = "";
  state.competitorId = "";
  if (state.seriesEntry?.path) {
    state.view = "participants";
    setUrl("push");
    showSeries();
  } else {
    state.view = "preview";
    setUrl("push");
    showPreview();
  }
}

function openContest(contestId, updateUrl = true) {
  const contestIndex = state.series.contests.findIndex((contest) => contest.id === contestId);
  if (contestIndex < 0) return showSeries();
  const contest = state.series.contests[contestIndex];
  const participants = state.index.participantsByContest[contestIndex];
  state.view = "participants";
  state.contestId = contest.id;
  state.competitorId = "";
  if (updateUrl) setUrl("push");
  elements.seriesView.hidden = true;
  elements.problemRatingView.hidden = true;
  elements.previewView.hidden = true;
  elements.reviewView.hidden = true;
  elements.participantControls.hidden = false;
  elements.detailView.hidden = false;
  updateSeriesMode();
  elements.detailView.replaceChildren();

  const heading = node("div", { className: "detail-header" }, [
    node("div", {}, [
      node("p", { className: "eyebrow", text: "CONTEST" }),
      node("h2", { id: "detail-title", text: contest.title, tabIndex: -1 }),
      node("p", { className: "detail-meta" }, [
        node("span", { text: new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(contest.startAt)) }),
        node("span", { text: `${participants.length.toLocaleString("zh-CN")} 位参赛者` }),
        ...(contest.rated === false ? [node("span", { className: "unrated-note", text: `Unrated：${contest.unratedReason}` })] : []),
      ]),
    ]),
    backButton(),
  ]);
  const shell = node("div", { className: "table-shell contest-table-shell", tabIndex: 0, "aria-label": "本场参赛者表" });
  const headRow = node("tr");
  ["比赛排名", "参赛者 / 学校", "赛前", "赛后", "变化"].forEach((label) => headRow.append(node("th", { scope: "col", text: label })));
  const body = node("tbody");
  const table = node("table", { className: "data-table fixed-table contest-table" }, [
    columnGroup([96, 250, 90, 90, 90]),
    node("thead", {}, [headRow]),
    body,
  ]);
  shell.append(table);
  const draw = () => renderVirtualRows({
    container: shell, body, items: participants, columns: 5,
    createRow({ competitor, participation }, index) {
      const row = node("tr");
      row.setAttribute("aria-rowindex", String(index + 2));
      row.append(node("td", { text: String(participation.contestRank) }));
      row.append(node("td", {}, [personButton(competitor, participation.contestRank)]));
      row.append(node("td", {}, [ratingNode(participation.before)]));
      row.append(node("td", {}, [ratingNode(participation.after)]));
      row.append(node("td", { className: deltaClass(participation.delta), text: formatDelta(participation.delta) }));
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

function shortContestTitle(contest, contestIndex) {
  if (contest.shortTitle) return contest.shortTitle;
  const chinese = contest.title.match(/第([^（）()]+)场/u)?.[0];
  if (chinese) return chinese;
  const numeric = contest.title.match(/[（(](\d+)[）)]/u)?.[1];
  return numeric ? `第${numeric}场` : `第${contestIndex + 1}场`;
}

function renderProblemTable(rows, showProblemNames) {
  elements.problemNameCol.hidden = !showProblemNames;
  elements.problemNameColumn.hidden = !showProblemNames;
  const fragment = document.createDocumentFragment();
  for (const { contest, problem } of rows) {
    const row = node("tr");
    row.append(node("td", { text: contest.title, title: contest.title }));
    row.append(node("td", {
      className: "problem-identity-cell",
      title: [problem.index, problem.name, contest.title].filter(Boolean).join(" · "),
      "aria-label": [problem.index, problem.name, contest.title].filter(Boolean).join("，"),
    }, [
      node("span", { className: "problem-identity-content" }, [
        node("span", { className: "problem-identity-index", text: problem.index }),
        ...(problem.name ? [node("span", { className: "problem-identity-name", text: problem.name })] : []),
        node("small", { className: "identity-secondary", text: contest.title }),
      ]),
    ]));
    if (showProblemNames) {
      row.append(node("td", {
        className: "problem-name-cell",
        text: problem.name,
        title: problem.name,
      }));
    }
    row.append(node("td", {}, [ratingNode(problem.rating)]));
    row.append(node("td", { className: "problem-team-counts" }, [
      node("span", { text: problem.solvedCount.toLocaleString("zh-CN") }),
      node("span", { className: "problem-team-count-separator", text: "/" }),
      node("span", { text: problem.participantCount.toLocaleString("zh-CN") }),
    ]));
    fragment.append(row);
  }
  if (!rows.length) {
    const emptyRow = node("tr", { className: "problem-table-empty" });
    emptyRow.append(node("td", { colSpan: showProblemNames ? 5 : 4, text: "未选择场次" }));
    fragment.append(emptyRow);
  }
  elements.problemTableBody.replaceChildren(fragment);
  elements.problemContestColumn.removeAttribute("aria-sort");
  elements.problemRatingColumn.removeAttribute("aria-sort");
  const sortedColumn = state.problemSort === "rating"
    ? elements.problemRatingColumn
    : elements.problemContestColumn;
  sortedColumn.setAttribute("aria-sort", state.problemOrder === "asc" ? "ascending" : "descending");
  const indicator = state.problemOrder === "asc" ? "↑" : "↓";
  elements.problemContestSortIndicator.textContent = state.problemSort === "contest" ? indicator : "";
  elements.problemRatingSortIndicator.textContent = state.problemSort === "rating" ? indicator : "";
}

function setProblemSort(sort) {
  state.problemOrder = state.problemSort === sort && state.problemOrder === "asc" ? "desc" : "asc";
  state.problemSort = sort;
  applyProblemRatingState();
}

function emphasizeProblemCurve(contestId = "") {
  for (const element of elements.problemChart.querySelectorAll("[data-curve-id]")) {
    const active = element.getAttribute("data-curve-id") === contestId;
    element.classList.toggle("is-muted", Boolean(contestId) && !active);
    element.classList.toggle("is-active", Boolean(contestId) && active);
  }
}

function renderProblemChart() {
  if (!state.problemSeries) return;
  const selectedIds = state.problemSeries.contests
    .filter(({ id }) => state.problemSelectedContestIds.has(id))
    .map(({ id }) => id);
  const curves = buildDifficultyCurves(state.problemSeries, selectedIds);
  const figure = node("figure", { className: "problem-chart-figure" });
  const legend = node("div", { className: "problem-chart-legend", "aria-label": "场次筛选和图例" });
  const allContestIds = state.problemSeries.contests.map(({ id }) => id);
  const quickSelections = [
    { text: "全选", contestIds: allContestIds },
    { text: "全不选", contestIds: [] },
  ];
  if (state.problemSeries.seriesId === "2025-2026") {
    quickSelections.push(
      {
        text: "仅 ICPC",
        contestIds: allContestIds.filter((contestId) => contestId.startsWith("icpc")),
      },
      {
        text: "仅 CCPC",
        contestIds: allContestIds.filter((contestId) => contestId.startsWith("ccpc")),
      },
    );
  }
  const legendActions = node("span", { className: "problem-legend-actions" },
    quickSelections.map(({ text, contestIds }) => node("button", {
      className: "problem-legend-action",
      type: "button",
      text,
      disabled: contestIds.length === selectedIds.length
        && contestIds.every((contestId) => state.problemSelectedContestIds.has(contestId)),
      onclick: () => {
        state.problemSelectedContestIds = new Set(contestIds);
        applyProblemRatingState();
      },
    })),
  );
  legend.append(legendActions);
  state.problemSeries.contests.forEach((contest, contestIndex) => {
    const selected = state.problemSelectedContestIds.has(contest.id);
    const color = problemCurveColor(contestIndex);
    const legendButton = node("button", {
      className: `problem-legend-item${selected ? "" : " is-unselected"}`,
      type: "button",
      title: contest.title,
      "aria-pressed": String(selected),
      "data-curve-id": contest.id,
    }, [
      node("span", { className: "problem-legend-swatch", "aria-hidden": "true" }),
      node("span", { text: shortContestTitle(contest, contestIndex) }),
    ]);
    legendButton.querySelector(".problem-legend-swatch").style.backgroundColor = color;
    legendButton.addEventListener("click", () => {
      if (selected) state.problemSelectedContestIds.delete(contest.id);
      else state.problemSelectedContestIds.add(contest.id);
      applyProblemRatingState();
    });
    if (selected) {
      const emphasize = () => emphasizeProblemCurve(contest.id);
      legendButton.addEventListener("mouseenter", emphasize);
      legendButton.addEventListener("focus", emphasize);
      legendButton.addEventListener("mouseleave", () => emphasizeProblemCurve());
      legendButton.addEventListener("blur", () => emphasizeProblemCurve());
    }
    legend.append(legendButton);
  });

  if (!curves.length) {
    figure.append(
      node("div", { className: "problem-chart-empty" }, [
        node("p", { className: "empty", text: "请选择至少一场比赛以显示难度曲线。" }),
      ]),
      legend,
    );
    elements.problemChart.replaceChildren(figure);
    return;
  }

  const allRatings = curves.flatMap(({ points }) => points.map(({ problem }) => problem.rating));
  const rawMin = Math.min(...allRatings);
  const rawMax = Math.max(...allRatings);
  const min = Math.floor((rawMin - 100) / 100) * 100;
  const max = Math.max(min + 100, Math.ceil((rawMax + 100) / 100) * 100);
  const maxSlots = Math.max(...curves.map(({ slotCount }) => slotCount));
  const left = 62, right = 28, top = 28, bottom = 54, height = 410;
  const width = Math.max(320, Math.floor(elements.problemChart.clientWidth || 900));
  const slotWidth = (width - left - right) / maxSlots;
  const x = (difficultyIndex) => left + (difficultyIndex + .5) * slotWidth;
  const y = (rating) => top + (max - rating) * (height - top - bottom) / (max - min);

  const stage = node("div", { className: "problem-chart-stage" });
  const svg = svgNode("svg", {
    class: "problem-rating-chart",
    viewBox: `0 0 ${width} ${height}`,
    role: "img",
    "aria-label": `${state.problemSeries.title}题目难度曲线`,
    "aria-describedby": "problem-chart-description",
  });
  const description = svgNode("desc", { id: "problem-chart-description" });
  description.textContent = "每场比赛的题目按预测 Rating 从易到难排列，横向长度与题目数量成正比。";
  svg.append(description);

  for (let tick = 0; tick <= 5; tick += 1) {
    const value = Math.round((min + (max - min) * tick / 5) / 100) * 100;
    const gridY = y(value);
    svg.append(svgNode("line", {
      class: "chart-grid",
      x1: left,
      x2: width - right,
      y1: gridY,
      y2: gridY,
    }));
    const label = svgNode("text", {
      class: "chart-axis",
      x: left - 9,
      y: gridY + 4,
      "text-anchor": "end",
    });
    label.textContent = String(value);
    svg.append(label);
  }

  const tooltip = node("div", {
    className: "chart-tooltip problem-chart-tooltip",
    hidden: true,
    role: "status",
  });
  curves.forEach((curve) => {
    const color = problemCurveColor(curve.contestIndex);
    const screenPoints = curve.points.map(({ problem, ...point }) => ({
      ...point,
      problem,
      x: x(point.difficultyIndex),
      y: y(problem.rating),
    }));
    const path = svgNode("path", {
      class: "problem-curve-line",
      d: monotoneCubicPath(screenPoints),
      stroke: color,
      tabindex: 0,
      role: "img",
      "aria-label": `${curve.contest.title}，${curve.slotCount} 道题`,
      "data-curve-id": curve.contest.id,
    });
    const emphasize = () => emphasizeProblemCurve(curve.contest.id);
    const clearEmphasis = () => emphasizeProblemCurve();
    const positionCurveTooltip = (event) => {
      const middle = screenPoints[Math.floor(screenPoints.length / 2)];
      if (event.type === "mouseenter" || event.type === "mousemove") {
        const bounds = stage.getBoundingClientRect();
        tooltip.style.left = `${Math.min(width - 220, Math.max(4, event.clientX - bounds.left + 10))}px`;
        tooltip.style.top = `${Math.max(4, event.clientY - bounds.top - 46)}px`;
      } else {
        tooltip.style.left = `${Math.min(width - 220, middle.x + 10)}px`;
        tooltip.style.top = `${Math.max(4, middle.y - 48)}px`;
      }
    };
    const showCurve = (event) => {
      emphasize();
      tooltip.hidden = false;
      tooltip.replaceChildren(node("strong", { text: curve.contest.title }));
      positionCurveTooltip(event);
    };
    const hideCurve = () => {
      tooltip.hidden = true;
      clearEmphasis();
    };
    const hoverPath = svgNode("path", {
      class: "problem-curve-hover-target",
      d: monotoneCubicPath(screenPoints),
      "aria-hidden": "true",
      "data-curve-id": curve.contest.id,
    });
    path.addEventListener("focus", showCurve);
    path.addEventListener("blur", hideCurve);
    hoverPath.addEventListener("mouseenter", showCurve);
    hoverPath.addEventListener("mousemove", positionCurveTooltip);
    hoverPath.addEventListener("mouseleave", hideCurve);
    svg.append(path, hoverPath);

    screenPoints.forEach((point) => {
      const dot = svgNode("circle", {
        class: "problem-curve-point",
        cx: point.x,
        cy: point.y,
        r: 3.5,
        fill: color,
        "data-curve-id": curve.contest.id,
      });
      const hit = svgNode("circle", {
        class: "problem-curve-hit",
        cx: point.x,
        cy: point.y,
        r: 11,
        tabindex: 0,
        role: "img",
        "aria-label": `${curve.contest.title}，${point.problem.index}${point.problem.name ? ` ${point.problem.name}` : ""}，Rating ${point.problem.rating}`,
        "data-curve-id": curve.contest.id,
      });
      const show = () => {
        emphasize();
        tooltip.hidden = false;
        tooltip.replaceChildren(
          node("strong", { text: `${curve.contest.title} · ${point.problem.index}` }),
          ...(point.problem.name ? [node("span", { text: point.problem.name })] : []),
          node("span", {}, [document.createTextNode("Rating "), ratingNode(point.problem.rating)]),
        );
        tooltip.style.left = `${Math.min(width - 220, point.x + 10)}px`;
        tooltip.style.top = `${Math.max(4, point.y - 72)}px`;
      };
      const hide = () => {
        tooltip.hidden = true;
        clearEmphasis();
      };
      hit.addEventListener("mouseenter", show);
      hit.addEventListener("focus", show);
      hit.addEventListener("mouseleave", hide);
      hit.addEventListener("blur", hide);
      svg.append(dot, hit);
    });

  });

  stage.append(svg, tooltip);
  figure.append(
    stage,
    legend,
    node("figcaption", {
      className: "chart-note",
      text: "圆点为真实题目预测值；平滑线仅连接相邻题目，不表示题目之间存在额外预测。每场曲线的横向长度与题目数量成正比。",
    }),
  );
  elements.problemChart.replaceChildren(figure);
}

function scheduleProblemChart() {
  if (state.problemChartFrame) cancelAnimationFrame(state.problemChartFrame);
  state.problemChartFrame = requestAnimationFrame(() => {
    state.problemChartFrame = 0;
    if (state.view === "problem-rating" && !elements.problemRatingView.hidden) renderProblemChart();
  });
}

function applyProblemRatingState({ updateUrl = true } = {}) {
  if (!state.problemSeries) return;
  const selectedIds = state.problemSeries.contests
    .filter(({ id }) => state.problemSelectedContestIds.has(id))
    .map(({ id }) => id);
  const rows = sortProblemRows(
    flattenProblemRatings(state.problemSeries, selectedIds),
    state.problemSort,
    state.problemOrder,
  );
  elements.problemResultCount.textContent = `${rows.length.toLocaleString("zh-CN")} 道题 · ${selectedIds.length} / ${state.problemSeries.contests.length} 场`;
  elements.problemRatingSummary.textContent = `${state.problemSeries.contests.length} 场比赛 · ${state.problemSeries.contests.reduce((total, contest) => total + contest.problems.length, 0)} 道题`;
  renderProblemChart();
  renderProblemTable(rows, problemSeriesHasNames(state.problemSeries));
  if (updateUrl) setUrl();
}

async function showProblemRating(query = {}, updateUrl = true) {
  if (!state.problemAvailableSeries.has(state.seriesId)) return showSeries();
  state.view = "problem-rating";
  state.contestId = "";
  state.competitorId = "";
  updateSeriesMode();
  elements.participantControls.hidden = true;
  elements.seriesView.hidden = true;
  elements.detailView.hidden = true;
  elements.problemRatingView.hidden = true;
  elements.previewView.hidden = true;
  elements.reviewView.hidden = true;
  elements.status.hidden = false;
  elements.status.textContent = "正在加载题目 Rating…";
  const loaded = await problemRatingStore.getSeries(state.seriesId);
  const canonicalContestIds = state.series.contests.map(({ id }) => id);
  const problemContestIds = loaded.series.contests.map(({ id }) => id);
  if (canonicalContestIds.length !== problemContestIds.length
      || canonicalContestIds.some((id, index) => id !== problemContestIds[index])) {
    throw new TypeError(`problem rating series ${state.seriesId}: contest order does not match participant series`);
  }
  state.problemSeries = loaded.series;
  const available = new Set(problemContestIds);
  state.problemSelectedContestIds = query.selectedContestIds === null
    || query.selectedContestIds === undefined
    ? new Set(problemContestIds)
    : new Set(query.selectedContestIds.filter((id) => available.has(id)));
  state.problemSort = query.sort === "rating" ? "rating" : "contest";
  state.problemOrder = query.order === "desc" ? "desc" : "asc";
  elements.problemRatingTitle.textContent = state.problemSeries.title;
  elements.status.hidden = true;
  elements.problemRatingView.hidden = false;
  applyProblemRatingState({ updateUrl: false });
  if (updateUrl) setUrl("push");
  else setUrl();
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
    row.append(node("td", { className: deltaClass(participation.delta), text: formatDelta(participation.delta) }));
    body.append(row);
  });
  return node("div", { className: "compact-table-wrap", tabIndex: 0 }, [node("table", { className: "data-table compact-table" }, [node("thead", {}, [head]), body])]);
}

function openCompetitor(competitorId, updateUrl = true) {
  const competitor = state.index.competitorById.get(competitorId);
  if (!competitor) return showSeries();
  state.view = "participants";
  state.competitorId = competitor.id;
  state.contestId = "";
  if (updateUrl) setUrl("push");
  elements.seriesView.hidden = true;
  elements.problemRatingView.hidden = true;
  elements.previewView.hidden = true;
  elements.reviewView.hidden = true;
  elements.participantControls.hidden = false;
  elements.detailView.hidden = false;
  updateSeriesMode();
  const heading = node("div", { className: "detail-header" }, [
    node("div", {}, [
      node("p", { className: "eyebrow", text: "PARTICIPANT" }),
      node("h2", { id: "detail-title", text: competitor.member, tabIndex: -1 }),
      node("p", { className: "detail-meta" }, [
        ...(competitor.school ? [node("span", { text: competitor.school })] : []),
        node("span", { text: `系列排名 #${competitor.rank}` }),
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

function updateSeriesNavigation() {
  for (const button of elements.seriesList.querySelectorAll(".series-link")) {
    const active = button.dataset.seriesId === state.seriesId;
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  }
}

async function loadSeries(seriesId, queryState = {}) {
  const loadVersion = ++seriesLoadVersion;
  state.view = "loading";
  elements.status.hidden = false;
  elements.status.textContent = "正在加载数据…";
  elements.seriesView.hidden = true;
  elements.problemRatingView.hidden = true;
  elements.previewView.hidden = true;
  elements.reviewView.hidden = true;
  elements.detailView.hidden = true;
  const entry = state.siteIndex.series.find((item) => item.id === seriesId);
  if (!entry) throw new Error(`Unknown series: ${seriesId}`);
  const [loaded, previews] = await Promise.all([
    entry.path ? store.getSeries(seriesId) : null,
    entry.previewPath || entry.previews ? previewStore.getPreviews(entry) : [],
  ]);
  if (loadVersion !== seriesLoadVersion) return;
  state.seriesId = entry.id;
  state.seriesEntry = entry;
  state.series = loaded?.series ?? null;
  state.index = loaded?.index ?? null;
  state.previews = previews;
  state.review = null;
  state.reviewContest = null;
  state.reviewAnalysis = null;
  state.reviewMetric = queryState.reviewMetric ?? "power";
  state.reviewSort = queryState.reviewSort ?? "actualRank";
  state.reviewOrder = queryState.reviewOrder ?? "asc";
  const preview = previews.find(p => p.id === queryState.previewContest) ?? previews[0] ?? null;
  state.preview = preview;
  state.previewPower = preview
    ? buildPreviewPower(preview.teams, preview.metricSources.map(({ id }) => id))
    : new Map();
  state.previewRanks = preview
    ? buildPreviewRanks(preview.teams, preview.metricSources.map(({ id }) => id))
    : new Map();
  state.problemSeries = null;
  state.problemSelectedContestIds = new Set();
  updateSeriesNavigation();
  state.query = queryState.query ?? state.query;
  const requestedSchools = queryState.schools ?? state.schools;
  const showRequestedPreview = queryState.view === "preview" && state.preview;
  state.availableSchools = showRequestedPreview || (queryState.view === "review" && state.preview) || !state.series
    ? listPreviewSchools(state.preview.teams)
    : listSchools(state.series.competitors);
  const available = new Set(state.availableSchools);
  state.schools = requestedSchools.filter((school) => available.has(school));
  const previewSorts = new Set([
    "school", "name", "members", "power", "medals",
    ...(state.preview?.metricSources.map(({ id }) => id) ?? []),
  ]);
  state.previewSort = previewSorts.has(queryState.previewSort) ? queryState.previewSort : "power";
  state.previewOrder = queryState.previewOrder === "asc" ? "asc" : "desc";
  elements.searchInput.value = state.query;
  renderSchoolControls();
  updateSeriesMode();
  if (queryState.view === "review" && entry.reviewPath) {
    await showReview(queryState);
  } else if (showRequestedPreview || !state.series) {
    elements.status.hidden = true;
    showPreview();
  } else if (queryState.view === "problem-rating" && state.problemAvailableSeries.has(state.seriesId)) {
    await showProblemRating(queryState, false);
  } else {
    elements.status.hidden = true;
    if (queryState.competitor && state.index.competitorById.has(queryState.competitor)) {
      openCompetitor(queryState.competitor, false);
    } else if (queryState.contest
        && state.series.contests.some((contest) => contest.id === queryState.contest)) {
      openContest(queryState.contest, false);
    } else {
      showSeries();
    }
  }
  setUrl();
}

async function initialize() {
  const index = await store.getIndex();
  state.siteIndex = index;
  try {
    const problemIndex = await problemRatingStore.getIndex();
    state.problemAvailableSeries = new Set(problemIndex.series.map(({ id }) => id));
  } catch (error) {
    console.error("Unable to load problem rating index", error);
    state.problemAvailableSeries = new Set();
  }
  const query = {
    ...readQueryState(location.href),
    ...readProblemRatingQuery(location.href),
    ...readPreviewQuery(location.href),
    ...readReviewQuery(location.href),
  };
  if (["preview", "review"].includes(new URL(location.href).searchParams.get("view"))) query.view = new URL(location.href).searchParams.get("view");
  for (const entry of index.series) {
    const button = node("button", {
      type: "button",
      className: "series-link",
      text: entry.title,
    });
    button.dataset.seriesId = entry.id;
    button.addEventListener("click", () => {
      if (entry.id === state.seriesId) openSeriesHome();
      else {
        let queryState = {};
        if (state.view === "problem-rating" && state.problemAvailableSeries.has(entry.id)) {
          queryState = { view: "problem-rating", selectedContestIds: null };
        } else if (!entry.path && (entry.previewPath || entry.previews)) {
          queryState = { view: "preview" };
        }
        loadSeries(entry.id, queryState).catch(showError);
      }
    });
    elements.seriesList.append(button);
  }
  const seriesId = index.series.some((entry) => entry.id === query.series) ? query.series : index.defaultSeriesId;
  await loadSeries(seriesId, query);
}

elements.searchInput.addEventListener("input", () => applySearch());
elements.clearSearchButton.addEventListener("click", () => {
  elements.searchInput.value = "";
  elements.schoolFilterSearch.value = "";
  state.query = "";
  state.schools = [];
  setSchoolMenu(false);
  renderSchoolControls();
  applySearch();
  elements.searchInput.focus();
});
elements.schoolFilterButton.addEventListener("click", () => {
  setSchoolMenu(elements.schoolFilterMenu.hidden);
});
elements.schoolFilterSearch.addEventListener("input", renderSchoolOptions);
elements.schoolFilter.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !elements.schoolFilterMenu.hidden) {
    setSchoolMenu(false);
    elements.schoolFilterButton.focus();
  }
});
document.addEventListener("click", (event) => {
  if (!elements.schoolFilter.contains(event.target)) setSchoolMenu(false);
});
elements.participantRatingTab.addEventListener("click", openSeriesHome);
elements.problemRatingTab.addEventListener("click", () => {
  showProblemRating({ selectedContestIds: null }, true).catch(showError);
});
elements.previewTab.addEventListener("click", () => {
  if (state.view === "preview") return;
  showPreview(true);
});
elements.previewContestSelect.addEventListener("change", () => {
  choosePreview(elements.previewContestSelect.value);
  elements.previewScroll.scrollTop = 0;
  showPreview(true);
});
elements.reviewTab.addEventListener("click", () => {
  if (state.view !== "review") showReview({}, true).catch(showError);
});
elements.reviewContestSelect.addEventListener("change", () => {
  showReview({ reviewContest: elements.reviewContestSelect.value }, true).catch(showError);
});
elements.reviewScroll.addEventListener("scroll", scheduleReviewRows, { passive: true });
new ResizeObserver(scheduleReviewRows).observe(elements.reviewScroll);
elements.problemContestSort.addEventListener("click", () => setProblemSort("contest"));
elements.problemRatingSort.addEventListener("click", () => setProblemSort("rating"));
elements.seriesScroll.addEventListener("scroll", scheduleSeriesRows, { passive: true });
elements.previewScroll.addEventListener("scroll", schedulePreviewRows, { passive: true });
window.addEventListener("resize", () => {
  scheduleSeriesRows();
  scheduleProblemChart();
  schedulePreviewRows();
  scheduleReviewRows();
});
window.addEventListener("popstate", () => {
  const query = {
    ...readQueryState(location.href), ...readProblemRatingQuery(location.href),
    ...readPreviewQuery(location.href), ...readReviewQuery(location.href),
  };
  const view = new URL(location.href).searchParams.get("view");
  if (["preview", "review"].includes(view)) query.view = view;
  const seriesId = state.siteIndex.series.some(entry => entry.id === query.series)
    ? query.series : state.siteIndex.defaultSeriesId;
  loadSeries(seriesId, query).catch(showError);
});

initialize().catch(showError);
