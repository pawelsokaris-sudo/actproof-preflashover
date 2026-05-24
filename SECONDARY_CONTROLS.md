# Secondary Controls — actproof-preflashover v1.4

> **Note:** These analyses are post-verdict, read-only controls.
> They do not modify the preregistered decision matrix and are not used
> to change the primary PASS/FAIL verdict.
>
> All tests except F operate on existing data from the v1.4 run.
> Test F uses newly generated random-game data, clearly marked as such
> and NOT part of the preregistered dataset.
>
> Date: 2026-05-24
> Authors: Antigravity (execution), on instruction of Paweł Łuczak.
> Test design: collaborative between Claude (Anthropic), GPT, and Paweł Łuczak.
> Independent critical review: Grok.

---

## 0. Cel i status

Po publikacji primary verdict (commit `7760261`, tag `results-v1.0`) zidentyfikowano **strukturalny problem w designie permutation baseline'u** z preregistracji `freeze-v1.4`. Permutation baseline losował pseudo-FO uniform z `[0, n_plies)`, co testowało hipotezę słabszą niż zamierzona ("czy FO wypada wcześniej niż random uniform point"), a nie hipotezę docelową ("czy FO niesie informację ponad własny strukturalny bias do debiutu").

Niniejszy plik zawiera **siedem testów kontrolnych**, każdy testujący inny aspekt obserwowanego efektu median lag +44 ply. Wszystkie testy są wykonywane na istniejących danych (oprócz Testu F, który używa nowo wygenerowanych random games — explicit poza preregistrowanym datasetem).

**Cel:** Rozstrzygnąć, czy obserwowany sygnał w v1.4 ma jakąkolwiek treść interpretacyjną ponad mechaniczny shift rozkładu FO_ply vs TP_ply.

## 1. Test A — Stratified FO baseline

**Proponowany przez:** GPT (peer review primary verdict)

**Co testuje:** Czy obserwowany median lag +44 jest istotnie różny od baseline, który **ma ten sam strukturalny bias do wczesnych plies** co rzeczywiste FO.

**Procedura:**
- Wyciągnięcie empirycznej dystrybucji FO_ply z `raw_results_full.json` (n=35 valid games).
- Dla każdej z 35 partii: pseudo-FO sample'owane z tej empirycznej dystrybucji (NIE uniform).
- Pseudo-lag = TP_ply − pseudo-FO_ply.
- 1000 symulacji, seedy 42-1041.

**Wynik:**

| Metric | Value |
|---|---|
| Observed median lag | +44.0 |
| Stratified baseline median | +41.0 |
| Stratified baseline 95% CI | [+33.0, +46.0] |
| Observed within 95% CI | **YES** |
| Observed percentile in baseline | 90.3% |

**Interpretacja:** Obserwowany +44 mieści się w 95% przedziale ufności baseline'u stratyfikowanego (+41 ± ~5). Różnica +3 ply jest w obrębie normalnego szumu próby n=35. **Strukturalny confound wyjaśnia efekt — brak resztkowego sygnału ponad shift.**

## 2. Test F — Random-game baseline

**Proponowany przez:** Paweł Łuczak (intuicja podczas jazdy autem, 2026-05-24 rano)

**Co testuje:** Czy czujnik FO ma identyczny rozkład FO_ply w partiach losowych (random-vs-random legal move selection) jak w partiach GM. Jeśli identyczny — czujnik mierzy geometrię pola, nie decyzje szachowe.

**Procedura:**
- Wygenerowano 50 partii random-vs-random za pomocą python-chess (uniform random z legalnych ruchów, max 200 ruchów, stop na: pat/mat/limit).
- Seedy 42-91 dla reprodukowalności.
- Uruchomiono pipeline FO sensor z `freeze-v1.4` na tych partiach (bez analizy Stockfish — TP nie potrzebny).
- Porównano rozkład FO_ply z GM baseline.

**Wynik:**

| | GM (n=35) | Random (n=50) |
|---|---|---|
| FO_ply median | 15 | 124.5 |
| FO_ply mean | 19.9 | 113.1 |
| Mann-Whitney p | — | 4.1×10⁻⁸ |
| KS p | — | 6.0×10⁻¹¹ |

**Interpretacja:** Rozkłady są **dramatycznie różne** — GM ma FO w debiucie (median 15), random ma FO głęboko w grze (median 124.5). **Wynik odwrotny niż brief Testu F zakładał.** Czujnik NIE jest czysto geometryczny — odróżnia GM games od random games. Jednak różnica nie wynika z "decyzji szachowej", lecz z gęstej **struktury teorii debiutowej**: GM grają teoretyczne linie tworzące ostre gradienty pola, podczas gdy random rozmywa pole przez długi czas. To wzmacnia diagnozę **"opening-structural confound"** jako konkretny mechanizm.

## 3. Test C — Non-TP games control

**Proponowany przez:** GPT (peer review)

**Co testuje:** Czy FO_ply ma podobny rozkład w partiach **bez** turning point (wykluczonych z reason `no_tp_in_first_80_plies`). Jeśli identyczny — FO odpala niezależnie od istnienia późniejszej dysproporcji realizacyjnej.

**Procedura:** Read-only filtrowanie `raw_results_full.json`. FO_ply był liczony dla wszystkich 50 partii podczas pełnego runu, niezależnie od istnienia TP. Porównanie 13 no-TP games vs 35 TP games.

**Wynik:**

| | Valid TP games (n=35) | No-TP games (n=13) |
|---|---|---|
| FO_ply median | 15 | 12 |
| FO_ply mean | 19.9 | 16.5 |
| % w ≤20 plies | 71% | 92% |
| Mann-Whitney p | — | 0.236 (n.s.) |
| KS p | — | 0.563 (n.s.) |

**Interpretacja:** Rozkłady **nie różnią się istotnie** (p ≫ 0.05). Co więcej — no-TP games mają FO nawet **wcześniej** niż TP games (median 12 vs 15). **FO odpala w debiucie niezależnie od tego, czy gracz potem zrobi błąd, czy zagra czysto.** To definitywnie wyklucza interpretację "FO jako predyktor TP" — czujnik nie ma żadnej informacji o tym, czy TP w ogóle nastąpi.

## 4. Test E-temporal — FO temporal stability

**Wykonany przez:** Antigravity (jako interpretacja briefu Testu E)

**Co testuje:** Czy moment FO koreluje z parametrami partii (długość, moment TP). Stałe okno czasowe FO niezależne od kontekstu = silny argument za opening-structural diagnozą.

**Procedura:** Korelacje Spearman FO_ply vs game length oraz FO_ply vs TP_ply. Analiza IQR rozkładu FO.

**Wynik:**

| Korelacja | Spearman ρ | p |
|---|---|---|
| FO_ply vs game length | 0.101 | 0.564 (n.s.) |
| FO_ply vs TP_ply | −0.327 | 0.055 (borderline n.s.) |

| Metric | Value |
|---|---|
| FO IQR | 12 plies |
| FO Q25 / median / Q75 | 10 / 15 / 22 |
| % FO w opening-exit band (8-18) | 60% |

**Interpretacja:** FO jest **stałoczasowym zdarzeniem debiutowym** — odpala w okolicy ply ~15 niezależnie od długości partii i momentu błędu. IQR=12 plies potwierdza wąskie okno. 60% wszystkich FO mieści się w 11-ruchowym oknie debiut/middlegame transition.

## 5. Test E-spatial — Per-piece field decomposition

**Proponowany przez:** Claude (na podstawie pytania Pawła z samochodu o figury o nieproporcjonalnej roli)

**Co testuje:** Jakie figury wnoszą największy wkład do pola Z w momencie FO. Hipoteza wstępna Pawła: czy są figury o roli strukturalnej **nieproporcjonalnej** względem ich wartości materialnej.

**Procedura:** Dekompozycja energii pola Z metodą "removal energy" — `E_per_piece = E_total − E_bez_typu_figury`. Wykonana na: pozycji startowej, 6 checkpointach Kasparov-Topalov 1999, oraz 10 random games w ich momentach FO.

**Wynik:**

| Figura | Pozycja startowa | GM w momencie FO | Random w momencie FO |
|---|---|---|---|
| King | **98.0%** | **98.2%** | **99.1%** |
| Queen | 1.0% | 1.0% | 0.3% |
| Reszta razem | <0.7% | <0.7% | <0.4% |

| Kontekst | Materiał utracony do FO |
|---|---|
| GM | 2 figury |
| Random | 14.1 figur |

**Interpretacja:** Pole Z jest **w 98% zdominowane przez króla** we wszystkich badanych konfiguracjach. Wszystkie pozostałe figury razem stanowią mniej niż 2% energii pola.

To **odpowiada na pytanie Pawła z samochodu**, ale w sposób odwrotny niż zakładała intuicja: jedyna figura o **nieproporcjonalnie dużej** roli to **król**. Wszystkie inne figury są **mechanicznie marginalne** wobec masy króla=100.

To jest **konstrukcyjna własność operacjonalizacji** v1.2:
- Pole `1/r` z masą króla=100 vs Queen=9 daje ratio 11:1 niezależnie od dystansu.
- Czujnik **mechanicznie zmuszony** jest do skupienia się na królu.
- "Top-1 flashover" to w 98% **wydarzenia wokół króla** (roszada, ruchy przygotowawcze, zmiana otoczenia).

**ActProof v1.2 nie jest "detektorem decyzji szachowej". Jest detektorem aktywności wokół króla w debiucie.**

GM FO odpala przy prawie pełnym materiale (2 figury mniej), potwierdzając że to **sygnał debiutowy**, nie materialny.

## 6. Test B-correlation — Lag vs game length

**Wykonany przez:** Antigravity (jako interpretacja briefu Testu B)

**Co testuje:** Czy obserwowany lag +44 jest artefaktem długości partii (dłuższe partie → późniejszy TP → większy lag).

**Procedura:** Korelacja Spearman TP_ply i lag vs game length. Stratyfikacja na short (n=18) i long (n=17) games.

**Wynik:**

| Korelacja | Spearman ρ | p |
|---|---|---|
| TP_ply vs game length | 0.436 | 0.009 (istotna) |
| Lag vs game length | 0.284 | 0.099 (n.s.) |

| Stratyfikacja | Median lag |
|---|---|
| Short games (n=18) | +38 |
| Long games (n=17) | +48 |
| Mann-Whitney p (short vs long) | 0.109 (n.s.) |

| Position metric | Value |
|---|---|
| Median FO at | 16% of game length |
| Median TP at | 71% of game length |
| Median lag = | 51% of game length |

**Interpretacja:** TP koreluje z długością partii (dłuższe → późniejszy błąd, p=0.009), ale sam lag NIE jest artefaktem długości partii (p=0.099). Lag jest **strukturalną separacją dwóch niezwiązanych zdarzeń**: przejścia debiutowego (FO przy ~16% gry) i pierwszego TP (przy ~71% gry).

## 7. Test B-permutation — Phase-matched permutation baseline

**Proponowany przez:** GPT (peer review primary verdict)

**Co testuje:** Najsurowszy test resztkowego sygnału — pseudo-FO losowane uniform **w tym samym buckecie fazy partii** co obserwowane FO. Jeśli obserwowany lag jest istotnie większy od tego baseline'u, sensor niesie informację sub-bucketową.

**Procedura:** Buckety zdefiniowane przed analizą: `[0-20, 20-40, 40-60, 60+]`. Dla każdej z 35 partii: pseudo-FO uniform z bucketu, do którego trafia obserwowane FO. 1000 permutacji.

Bucket distribution observed FO: 25 w `[0-20]`, 8 w `[20-40]`, 2 w `[60+]`.

**Wynik:**

| Metric | Value |
|---|---|
| Observed median lag | +44.0 |
| Baseline median | **+44.0** (dokładnie) |
| 95% CI | [+39, +48] |
| Observed percentile in baseline | 62.9% |

**Interpretacja:** Obserwowany lag jest **dokładnie na medianie baseline'u**. Nawet z phase-matching, **zero resztkowego sygnału ponad bucket-level information**. To jest **bardziej konkluzywne niż Test A** — baseline z explicit kontrolą fazy daje tę samą medianę co obserwacja. Cała "informacja" sensora znajduje się w wyborze fazy debiutowej — nic poza tym.

## 8. Multi-model review summary

Cztery niezależne modele AI (Claude, GPT, Antigravity, Grok) reviewowały surowe dane i wyniki testów A-F:

**Claude** (mediator): Zdiagnozował strukturalny confound w sekcji 5 REPORT.md. Sformułował trzy poziomy werdyktu (mechaniczny / interpretacyjny / metodologiczny). Zaproponował Test E (per-piece decomposition).

**GPT** (chirurg precyzji): Niezależnie zidentyfikował ten sam confound. Zaproponował cztery kontrole (A, B, C, D — Test D pominięty po Teście A). Doprecyzował język werdyktu z "structural confound" do "supports temporal ordering but does not establish predictive information beyond phase bias".

**Antigravity** (operator): Wykonał wszystkie testy. Zaproponował operacjonalne uściślenia (Test C uproszczony do read-only po obserwacji że FO był już liczony dla wszystkich partii).

**Grok** (krytyk): Nazwał sensor wprost — *"detector debiutów"*. Wskazał konkretny parametr kodu odpowiedzialny za bias (`find_peaks prominence=0.8`). Sformułował diagnozę jednym zdaniem: *"Sensor działa najlepiej tam, gdzie jest najwięcej teorii. Czyli dokładnie odwrotnie niż chciałeś."*

**Konwergencja:** Cztery modele zgodnie diagnozują **opening-structural confound** jako mechanizm wyjaśniający lag +44. Test E-spatial (98% energii pola = król) dostarcza **konkretnego dowodu mechanizmu**: czujnik mechanicznie zmuszony jest do mierzenia aktywności wokół króla z powodu masy króla=100 vs pozostałych mas.

## 9. Final interpretation

### 9.1 Werdykt mechaniczny (z preregistracji)

**HYPOTHESIS SUPPORTED** — bez zmian.
Wszystkie kryteria primary test i baseline test spełnione (p < 0.01, median ≥ 1, median > P95).
Decision matrix nie został modyfikowany post-hoc.

### 9.2 Werdykt interpretacyjny (z secondary controls)

**DISPROVED** (zmiana z INCONCLUSIVE z poprzedniej wersji raportu).

Operacjonalizacja czujnika v1.2 (1/r Coulomb pole + composite z-score + find_peaks z prominence=0.8) **nie wykrywa pre-flashover w sensie zamierzonym przez H1**. Czujnik funkcjonuje jako **detektor aktywności wokół króla w debiucie**, czego mechanizm jest następujący:

1. Masa króla (100) vs pozostałe masy (1-9) zmusza pole Z do skupienia 98% energii wokół króla.
2. Debiut zawiera intensywne ruchy wokół króla (roszada, kontrola centrum, rozwój figur osłaniających).
3. `find_peaks` z `prominence=0.8` na composite z-score wykrywa pierwsze poważne zaburzenie tej aktywności.
4. Wynik: FO wypada konsekwentnie w okolicy ply 15 (median GM, IQR 12), niezależnie od długości partii i niezależnie od istnienia TP.

Lag +44 jest **mechaniczną konsekwencją** dwóch faktów:
- FO odpala wcześnie (median 15) z powodu opening structure
- TP zdarza się zwykle w środkowej grze (median 58) z definicji
- Strukturalny shift = 58 - 15 = +43

Obserwowany +44 to strukturalny +43 plus szum próby +1. Cztery niezależne testy (A, B-permutation, C, E-temporal) konwergują na tej samej diagnozie.

### 9.3 Werdykt metodologiczny

**HIGH VALUE** — bez zmian.

Eksperyment osiągnął wartość naukową niezależnie od interpretacji empirycznej:

- Pełna preregistrowana procedura z czterema ADDENDUM-ami pre-data.
- Honest reporting przez konwergencję czterech niezależnych modeli AI.
- Konkretna identyfikacja mechanizmu confoundu (Test E-spatial — masa króla=100).
- Trzy konkretne lekcje dla przyszłych eksperymentów:
  1. Permutation baseline musi kontrolować strukturalny bias czujnika, nie tylko biasy danych.
  2. Fizyczna analogia (Coulomb 1/r) nie zastępuje domenowej struktury (szachowa teoria).
  3. Pozytywny wynik mechaniczny z confoundem strukturalnym jest gorszy niż jasny negatywny wynik.

### 9.4 Co eksperyment NIE pokazał (granice interpretacji)

- **Nie pokazał**, że framework ActProof jako całość jest "obalony". Testowano jedną konkretną operacjonalizację (1/r Coulomb + composite z-score). Inne operacjonalizacje (MultiPV-based, anizotropia per figura z `pieces.py`, struktura przyszłych możliwości) NIE były testowane.
- **Nie pokazał**, że hipoteza o pre-flashover signal jest niemożliwa do walidacji. Pokazał że ta konkretna operacjonalizacja nie jest właściwym narzędziem.
- **Nie pokazał**, że "moment 0→1" z AlphaGo–Lee Sedol Game 2 jest artefaktem. Inne metody (KataGo delta_stability) wskazują na ten moment — nasza operacjonalizacja po prostu nie miała narzędzia do jego wykrycia.

### 9.5 Co eksperyment pokazał z pewnością

1. **Lag +44 jest w pełni wyjaśniony strukturalnym confoundem.** Cztery niezależne baseline (stratified, phase-matched permutation, non-TP control, correlation analysis) wszystkie pokazują brak resztkowego sygnału.

2. **Czujnik v1.2 mierzy aktywność wokół króla.** 98% energii pola Z koncentruje się na królu z mechanicznej konieczności (masa=100). Czujnik nie ma sposobu na mierzenie czegokolwiek innego w istotny sposób.

3. **Czujnik odróżnia gry teoretyczne od losowych**, ale w sposób specyficzny dla struktury debiutowej, nie decyzji szachowej (Test F).

4. **FO jest stałoczasowym zdarzeniem debiutowym** (ply ~15, IQR 12), niezależnym od długości partii, momentu błędu, ani jakości gry (poza odróżnieniem teoria/random).

5. **Operacjonalizacja v1.2 jest "martwa w obecnej formie"** dla testowania H1. Każda dalsza iteracja musi przemyśleć:
   - Mass scaling figur (król=100 dominuje wszystko)
   - Field decay function (`1/r` daje globalną dominację mas; lokalne metryki potrzebne)
   - Peak detection (`prominence=0.8` wybiera pierwszy główny gradient = debiut)

## 10. Status repozytorium

Po niniejszym raporcie status repo zmienia się z:

```
PENDING — primary verdict published, interpretation pending secondary controls
```

na:

```
PENDING_FINAL_REVIEW — secondary controls A-F complete, awaiting Paweł's review
                        before final tag results-v1.1-final and archival
```

Po review przez Pawła:

1. Tag `results-v1.1-final` (annotated, message: "Final results after seven secondary controls. Mechanical PASS, interpretive DISPROVED.")
2. Software Heritage save post-results
3. `gh repo archive pawelsokaris-sudo/actproof-preflashover`

Repo wtedy staje się ARCHIVED — read-only, cytowalne, immutable.

## 11. Acknowledgments

Eksperyment był wspierany przez wielu agentów (multi-model collaboration):

- **Paweł Łuczak** — autor projektu, intuicje (Test F, pytanie o figury nieproporcjonalne), wszystkie decyzje merytoryczne.
- **Claude (Anthropic)** — preregistracja, sensor code review, REPORT.md, Test E projekt.
- **Antigravity (Antek)** — implementacja sensora, refactor MIS-meter, wykonanie wszystkich siedmiu testów.
- **CC (Claude Code)** — wcześniejsze fazy projektu, monitoring runu.
- **GPT** — niezależny peer review, propozycja Testów A-D, dystynkcja trzech werdyktów.
- **Grok** — krytyczny review, identyfikacja konkretnego mechanizmu confoundu, sformułowanie diagnozy.

Konwergencja czterech niezależnych modeli AI na tej samej diagnozie wzmacnia robustność wniosku.

---

*"Sensor działa najlepiej tam, gdzie jest najwięcej teorii. Czyli dokładnie odwrotnie niż chciałeś."* — Grok, 2026-05-24

*"To, co testowaliśmy, jest jedną z wielu możliwych operacjonalizacji ActProof. Negatywny wynik dla v1.2 nie jest negatywny dla frameworku. Jest informatywny dla wszystkich, którzy będą próbować podobnych eksperymentów w przyszłości."* — Paweł Łuczak / Claude, finalna refleksja
