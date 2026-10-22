# Research: Agent-System-Abstraktion fuer Claude und GitHub Copilot

## Entscheidung 1: Scope strikt auf das Agentensystem begrenzen

**Decision**: Spec 015 behandelt ausschliesslich das Agentensystem des Kits: Agents, Skills, Hooks sowie die dazugehoerigen Instruktionen und Settings.

**Rationale**: Die korrigierte Zielsetzung verlangt keine allgemeine Erweiterung des gesamten Repos auf einen Multi-Integrationsbetrieb. Ein enger Scope verhindert, dass 015 in Dashboard-, Push-, Board- oder README-Themen ausfranst.

**Alternatives considered**:

- Allgemeines Repo-Integrationsprogramm: verworfen, weil es der korrigierten Zielsetzung widerspricht.
- Nur Copilot-Dateien ergaenzen ohne Agent-System-Abstraktion: verworfen, weil Claude-Annahmen im Kern verbleiben wuerden.

## Entscheidung 2: Pro Zielprojekt genau eine aktiv verwaltete Agent-Umgebung

**Decision**: Ein Zielprojekt hat in 015 genau eine aktiv vom Kit verwaltete Agent-Umgebung, entweder `claude` oder `copilot`.

**Rationale**: Die korrigierte Zielsetzung fordert keine parallele Vollverwaltung mehrerer Agent-Umgebungen im selben Projekt. Das Agentensystem soll abstrahiert, nicht zu einem allgemeinen Mehrfachintegrations-Manager ausgebaut werden.

**Alternatives considered**:

- Claude und Copilot gleichzeitig voll verwalten: verworfen, weil das die Spec unnoetig verbreitert.
- Keine feste aktive Agent-Umgebung modellieren: verworfen, weil Init-, Upgrade- und Doctor-Verhalten dann unscharf bleiben.

## Entscheidung 3: Claude bleibt Referenz, Copilot wird daran bausteinbezogen gespiegelt

**Decision**: Claude bleibt die bestehende Referenz des Agentensystems. Copilot wird daran bausteinbezogen gespiegelt, mit expliziter Einordnung je Baustein in Vollparitaet oder Annaeherung. Fuer Hooks ist eine bekannte Luecke in 015 ausgeschlossen.

**Rationale**: Die Zielsetzung fordert hohe funktionale Paritaet fuer Copilot, ohne unbelegte Behauptungen identischer Mechanik. Eine Bausteinmatrix ist ehrlicher und testbarer als eine pauschale Gleichheitsbehauptung.

**Alternatives considered**:

- Copilot pauschal als "nahezu gleich" behandeln: verworfen, weil das zu unscharf fuer spaetere Validierung ist.
- Copilot nur als reduzierten MVP spezifizieren: verworfen, weil das dem Paritaetsziel widerspricht.

## Entscheidung 4: Hook-Mechanik als Funktion, nicht als festes Claude-Dateimuster beschreiben

**Decision**: Hooks werden als Funktion des Agentensystems beschrieben. Fuer jede Agent-Umgebung wird festgelegt, ob die Funktion ueber native Hooks oder eine native oder nativ integrierte Ersatzmechanik erreicht wird. Fuer Copilot ist ein hook-loser `gap`-Zustand in 015 ausgeschlossen.

**Rationale**: Claude besitzt bereits konkrete Hook-Muster. Copilot muss dieselbe Funktion nicht ueber dieselbe Datei- oder Eventform anbieten. Entscheidend ist, ob der Kit-Baustein im Zielprojekt erreicht wird, wie dieser spaeter pruefbar ist und dass keine reine Nicht-Unterstuetzung als "approximate" kaschiert wird.

**Alternatives considered**:

- Claude-Hook-Form eins zu eins fuer Copilot vorschreiben: verworfen, weil das technisch nicht abgesichert ist.
- Hooks aus dem Agentensystem entfernen: verworfen, weil sie fuer Claude Teil des bestehenden Systems sind.
- Copilot ohne Hooks oder Hook-Ersatz als `gap` zulassen: verworfen, weil 015 fuer Copilot eine vorhandene, pruefbare Hook-Mechanik verlangt.

## Entscheidung 5: Agent-Artefakte pro Agent-Umgebung konkret benennen

**Decision**: Die Spec benennt fuer `claude` und `copilot` konkret die im Zielprojekt verwalteten Agent-Artefaktgruppen: Agents, Skills, Hooks oder Hook-Ersatz, Instruktionen und agentbezogene Settings. Repo- und Template-Pfade dienen nur als Quellenverweis.

**Rationale**: Init, Upgrade und Doctor brauchen einen klaren Vertragsgegenstand. Reine Sammelbegriffe wie "Copilot-Dateien" waeren nicht testbar genug.

**Alternatives considered**:

- Pflichtartefakte erst in der Implementierung festlegen: verworfen, weil Tasks und Tests dann unscharf blieben.
- Nur Settings behandeln, nicht aber Agents und Skills: verworfen, weil das den Kern des Agentensystems verfehlt.

## Entscheidung 6: Wechsel der Agent-Umgebung als geplanter Migrationsfall

**Decision**: Ein Wechsel eines Projekts von `claude` auf `copilot` oder umgekehrt wird als geplanter Migrationsfall beschrieben, einschliesslich Konflikt- und Ersetzungsplanung.

**Rationale**: Ohne diesen Fall wuerde 015 nur Neuinstallationen abdecken. Gleichzeitig verhindert die Migrationssicht, dass aus dem Wechsel eine implizite parallele Mehrfachverwaltung wird.

**Alternatives considered**:

- Wechsel nicht unterstuetzen: verworfen, weil bestehende Claude-Projekte sonst ausgeschlossen waeren.
- Wechsel als stillen Hintergrundprozess behandeln: verworfen, weil das gegen die Hoheit des Zielprojekts verstiesse.

## Entscheidung 7: Keine allgemeine Modellabstraktion in 015

**Decision**: Spec 015 fuehrt keine allgemeine Modellabstraktion, Profilsystematik oder anbieterneutrale Modellkonfiguration ein.

**Rationale**: Die korrigierte Zielsetzung begrenzt den Fokus auf das Agentensystem. Eine Modellabstraktion waere ein eigenes, deutlich breiteres Thema.

**Alternatives considered**:

- Modellprofile in 015 mitziehen: verworfen, weil das den Scope erneut aufblaehen wuerde.
- Jegliche model-bezogene Einstellungen ignorieren: verworfen, weil agentbezogene Settings weiterhin im Artefaktvertrag auftauchen koennen, aber ohne eigene allgemeine Abstraktionsinitiative.
