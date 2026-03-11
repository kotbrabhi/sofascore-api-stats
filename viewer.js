const state = {
  payload: null,
  filteredMatches: [],
  selectedMatchId: null,
};

const summaryGrid = document.querySelector("#summary-grid");
const standingsBody = document.querySelector("#standings-body");
const matchesList = document.querySelector("#matches-list");
const matchDetail = document.querySelector("#match-detail");
const statusMessage = document.querySelector("#status-message");
const matchesCount = document.querySelector("#matches-count");
const selectedMatchMeta = document.querySelector("#selected-match-meta");
const searchInput = document.querySelector("#match-search");
const filePicker = document.querySelector("#file-picker");
const loadDefaultButton = document.querySelector("#load-default");

function setStatus(message) {
  statusMessage.innerHTML = message;
}

function formatDate(timestamp) {
  if (!timestamp) return "Date inconnue";
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(timestamp * 1000));
}

function formatScore(score) {
  return score?.current ?? "-";
}

function getTeamColor(team) {
  return team?.teamColors?.primary || "#d6ddd6";
}

function createSummaryCard(label, value, note) {
  return `
    <article class="summary-card">
      <p class="summary-label">${label}</p>
      <p class="summary-value">${value}</p>
      <p class="summary-note">${note}</p>
    </article>
  `;
}

function renderSummary(payload) {
  const tournament = payload.tournament || {};
  const season = payload.season || {};
  const events = payload.events || [];
  const standings = payload.standings || [];

  summaryGrid.innerHTML = [
    createSummaryCard("Competition", tournament.name || "Botola Pro", tournament.country || ""),
    createSummaryCard("Saison", season.year || "-", `Round actuel: ${payload.currentRound ?? "-"}`),
    createSummaryCard("Matchs charges", String(events.length), "Matchs termines inclus dans le JSON"),
    createSummaryCard("Equipes", String(standings.length), "Classement complet"),
  ].join("");
}

function renderStandings(payload) {
  const standings = payload.standings || [];
  standingsBody.innerHTML = standings
    .map((row) => {
      const team = row.team || {};
      return `
        <tr>
          <td>${row.position ?? "-"}</td>
          <td>
            <span class="team-chip">
              <span class="team-dot" style="background:${getTeamColor(team)}"></span>
              ${team.name || "-"}
            </span>
          </td>
          <td>${row.points ?? "-"}</td>
          <td>${row.matches ?? "-"}</td>
          <td>${row.wins ?? "-"}</td>
          <td>${row.draws ?? "-"}</td>
          <td>${row.losses ?? "-"}</td>
          <td>${row.scoresFor ?? "-"}</td>
          <td>${row.scoresAgainst ?? "-"}</td>
          <td>${row.scoreDiffFormatted ?? "-"}</td>
        </tr>
      `;
    })
    .join("");
}

function matchesForSearch(payload, term) {
  const normalized = term.trim().toLowerCase();
  const events = payload.events || [];
  if (!normalized) return events;

  return events.filter((event) => {
    const haystack = [
      event.homeTeam?.name,
      event.awayTeam?.name,
      event.slug,
      event.round ? `round ${event.round}` : "",
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(normalized);
  });
}

function renderMatchList() {
  const matches = state.filteredMatches;
  matchesCount.textContent = `${matches.length} match${matches.length > 1 ? "s" : ""}`;

  if (!matches.length) {
    matchesList.innerHTML = `<div class="empty-state">Aucun match ne correspond a la recherche.</div>`;
    return;
  }

  matchesList.innerHTML = matches
    .map((event) => {
      const activeClass = event.id === state.selectedMatchId ? "is-active" : "";
      return `
        <article class="match-card ${activeClass}" data-match-id="${event.id}">
          <div class="match-card-top">
            <span>Round ${event.round ?? "-"}</span>
            <span>${formatDate(event.startTimestamp)}</span>
          </div>
          <div class="match-scoreline">
            <span class="team-name">${event.homeTeam?.name || "-"}</span>
            <span class="score-badge">${formatScore(event.homeScore)} - ${formatScore(event.awayScore)}</span>
            <span class="team-name">${event.awayTeam?.name || "-"}</span>
          </div>
        </article>
      `;
    })
    .join("");

  matchesList.querySelectorAll(".match-card").forEach((card) => {
    card.addEventListener("click", () => {
      state.selectedMatchId = Number(card.dataset.matchId);
      renderMatchList();
      renderMatchDetail();
    });
  });
}

function formatIncident(incident) {
  const time = incident.time != null ? `${incident.time}'${incident.addedTime ? `+${incident.addedTime}` : ""}` : "--";
  const playerName = incident.player?.name || incident.playerName || "";
  const text = [incident.incidentType, playerName, incident.text].filter(Boolean).join(" • ");

  return `
    <div class="timeline-item">
      <div class="timeline-time">${time}</div>
      <div>
        <div>${text || "Incident"}</div>
        <div class="timeline-text">${incident.homeScore ?? "-"} - ${incident.awayScore ?? "-"}</div>
      </div>
    </div>
  `;
}

function renderTeamStats(stats) {
  if (!stats?.length) {
    return `<p class="subtle">Aucune statistique d'equipe dans ce JSON.</p>`;
  }

  return `
    <table class="stats-table">
      <thead>
        <tr>
          <th>Stat</th>
          <th>Domicile</th>
          <th>Exterieur</th>
        </tr>
      </thead>
      <tbody>
        ${stats
          .map(
            (item) => `
              <tr>
                <td>${item.name || "-"}</td>
                <td>${item.homeValue ?? item.home ?? "-"}</td>
                <td>${item.awayValue ?? item.away ?? "-"}</td>
              </tr>
            `
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function playerMetric(player, key) {
  const value = player.statistics?.[key];
  return value ?? "-";
}

function renderPlayersTable(players, teamName) {
  if (!players?.length) {
    return `<p class="subtle">Aucun joueur pour ${teamName}.</p>`;
  }

  return `
    <table class="players-table">
      <thead>
        <tr>
          <th>Joueur</th>
          <th>Pos</th>
          <th>Role</th>
          <th>Min</th>
          <th>Note</th>
          <th>Buts</th>
          <th>Passes D</th>
        </tr>
      </thead>
      <tbody>
        ${players
          .map(
            (player) => `
              <tr>
                <td>${player.player?.name || "-"}</td>
                <td>${player.position || player.player?.position || "-"}</td>
                <td>${player.substitute ? "Remplacant" : "Titulaire"}</td>
                <td>${playerMetric(player, "minutesPlayed")}</td>
                <td>${playerMetric(player, "rating")}</td>
                <td>${playerMetric(player, "goals")}</td>
                <td>${playerMetric(player, "goalAssist")}</td>
              </tr>
            `
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function renderLineupPanel(side, label, team) {
  if (!side) {
    return `
      <div class="detail-block">
        <h3 class="section-title">${label}</h3>
        <p class="subtle">Lineup indisponible.</p>
      </div>
    `;
  }

  const allPlayers = [...(side.starters || []), ...(side.substitutes || [])];
  return `
    <div class="detail-block">
      <h3 class="section-title">${label} - ${team?.name || ""}</h3>
      <p class="formation-line">
        Formation: <strong>${side.formation || "-"}</strong>
        <span class="subtle">• titulaires ${side.starters?.length || 0}, banc ${side.substitutes?.length || 0}</span>
      </p>
      ${renderPlayersTable(allPlayers, team?.name || label)}
    </div>
  `;
}

function renderMatchDetail() {
  const match = state.filteredMatches.find((event) => event.id === state.selectedMatchId) || state.filteredMatches[0];

  if (!match) {
    selectedMatchMeta.textContent = "";
    matchDetail.className = "match-detail empty-state";
    matchDetail.textContent = "Aucun match a afficher.";
    return;
  }

  state.selectedMatchId = match.id;
  selectedMatchMeta.textContent = `Match ID ${match.id}`;
  matchDetail.className = "match-detail";

  const incidents = match.incidents || [];
  const lineups = match.lineups || {};

  matchDetail.innerHTML = `
    <section class="detail-head">
      <div class="detail-hero">
        <p class="eyebrow">Round ${match.round ?? "-"}</p>
        <div class="detail-scoreline">
          <span class="team-name">${match.homeTeam?.name || "-"}</span>
          <span class="detail-score">${formatScore(match.homeScore)} - ${formatScore(match.awayScore)}</span>
          <span class="team-name">${match.awayTeam?.name || "-"}</span>
        </div>
        <div class="detail-meta">
          <span>${formatDate(match.startTimestamp)}</span>
          <span>${match.status?.description || "Termine"}</span>
          <span>${lineups.confirmed ? "Lineups confirmes" : "Lineups non confirmes"}</span>
        </div>
      </div>

      <div class="detail-block">
        <h3 class="section-title">Incidents</h3>
        <div class="timeline">
          ${incidents.length ? incidents.slice(0, 18).map(formatIncident).join("") : `<p class="subtle">Aucun incident disponible.</p>`}
        </div>
      </div>
    </section>

    <section class="detail-grid">
      <div class="detail-block">
        <h3 class="section-title">Statistiques d'equipe</h3>
        ${renderTeamStats(match.teamStatistics)}
      </div>
      ${renderLineupPanel(lineups.home, "Domicile", match.homeTeam)}
      ${renderLineupPanel(lineups.away, "Exterieur", match.awayTeam)}
    </section>
  `;
}

function renderPayload(payload) {
  state.payload = payload;
  state.filteredMatches = [...(payload.events || [])];
  state.selectedMatchId = state.filteredMatches[0]?.id ?? null;

  renderSummary(payload);
  renderStandings(payload);
  renderMatchList();
  renderMatchDetail();
}

async function loadDefaultJson() {
  try {
    setStatus("Chargement de <code>data/botola-pro.json</code>...");
    const response = await fetch("data/botola-pro.json");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const payload = await response.json();
    renderPayload(payload);
    setStatus(`JSON charge depuis <code>data/botola-pro.json</code>.`);
  } catch (error) {
    console.error(error);
    setStatus(
      "Impossible de charger <code>data/botola-pro.json</code>. Lance un serveur local avec <code>python3 -m http.server</code> ou importe un fichier JSON manuellement."
    );
  }
}

function handleFileSelection(event) {
  const file = event.target.files?.[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = () => {
    try {
      const payload = JSON.parse(String(reader.result));
      renderPayload(payload);
      setStatus(`JSON charge depuis <code>${file.name}</code>.`);
    } catch (error) {
      console.error(error);
      setStatus("Le fichier selectionne n'est pas un JSON Botola valide.");
    }
  };
  reader.readAsText(file);
}

function handleSearch() {
  if (!state.payload) return;
  state.filteredMatches = matchesForSearch(state.payload, searchInput.value);
  if (!state.filteredMatches.some((event) => event.id === state.selectedMatchId)) {
    state.selectedMatchId = state.filteredMatches[0]?.id ?? null;
  }
  renderMatchList();
  renderMatchDetail();
}

loadDefaultButton.addEventListener("click", loadDefaultJson);
filePicker.addEventListener("change", handleFileSelection);
searchInput.addEventListener("input", handleSearch);

loadDefaultJson();
