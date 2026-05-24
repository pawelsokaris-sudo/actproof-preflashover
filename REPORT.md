# REPORT.md — Pre-Flashover Detection in Grandmaster Chess

> **Note (2026-05-22):** This report covers the primary preregistered run.
> Secondary controls A-D (recommended by independent review) are pending.
> Final interpretation will be released as `results-v1.1-final` after those
> controls are executed. See STATUS.md for current state.

**Projekt:** `actproof-preflashover`
**Stan:** ZAMKNIĘTY. Pełny preregistrowany run wykonany pod `freeze-v1.4`.
**Data raportu:** 2026-05-22
**Autor:** Paweł Łuczak, Sokaris Oprogramowanie / ActProof
**Współautor proceduralny:** Claude (Anthropic), w roli doradczej

---

## Jednoakapitowe streszczenie

Sprawdzaliśmy, czy nasz „czujnik ActProof" — analizujący geometrię pola informacyjnego na szachownicy — wykazuje sygnał poprzedzający duże dysproporcje realizacyjne (ruchy odbiegające od optymalnej trajektorii Stockfisha o ≥150 centypawnów) w 50 partiach turniejowych arcymistrzów. Mechaniczny werdykt zaprojektowany w preregistracji wyszedł **POZYTYWNY** (mediana lag = +44 ruchy, Wilcoxon p = 8.5 × 10⁻⁶, oba kryteria decyzyjne spełnione). Jednak druga analiza — rozkład samych pomiarów FO_ply i TP_ply — ujawniła, że obserwowane +44 ruchy lagu jest **strukturalnie nieodróżnialne** od artefaktu rozkładu czasowego naszych pomiarów. Czujnik FO ma silny bias do wczesnych ruchów partii (mediana ruch 15), TP z definicji występuje zwykle w środku partii (mediana ruch 58). Różnica strukturalna 58 − 15 = +43 ruchy jest bardzo blisko obserwowanej +44. **Uczciwy werdykt interpretacyjny: niejednoznaczny.** Sygnał istnieje w statystycznym sensie, ale przy obecnej operacjonalizacji nie da się go odseparować od artefaktu konstrukcji pomiaru.

---

## 1. Co właściwie sprawdzaliśmy (w prostym języku)

Wyobraź sobie fabrykę z siecią energetyczną. Po sieci płynie prąd — to jest fizyka. Maszyny obciążają sieć w różnych miejscach. Kiedy ktoś podłączy maszynę o dużej mocy, sieć drży, transformatory się grzeją, dochodzi do skoku napięcia.

Pytanie ActProof brzmi:

> Czy w samej fizyce sieci — w polu prądu, napięcia, obciążeń — widać coś **zanim** ktoś podłączy maszynę powodującą duży skok?

Albo równoważnie w szachach:

> Czy w geometrii pola figur na szachownicy widać sygnał **zanim** gracz wykona ruch powodujący dużą dysproporcję realizacyjną (czyli odbiegający od najlepszego ruchu o ≥150 centypawnów)?

Słowo **dysproporcja**, nie **błąd**. Bo „błąd" niesie ocenę. „Dysproporcja realizacyjna" opisuje fakt: zrealizowana trajektoria odbiega od trajektorii o najwyższej ocenie silnika. Powody odejścia — celowa ofiara, pomyłka, blef, próba skomplikowania pozycji — są poza zakresem tego eksperymentu. Mierzymy fakt strukturalny, nie interpretujemy intencji.

## 2. Co wyszło — mechaniczny werdykt

Pełen run pod `freeze-v1.4`:

```
n_total            : 50 partii (TWIC #1500–#1524, FIDE World Cup 2023 dominuje)
n_valid            : 35 partii (TP + FO oba wykryte)
n_excluded         : 15 (13 × brak TP w pierwszych 80 ruchach, 2 × position_timeout)

median lag         : +44 ply
mean lag           : +35.6 ply
Wilcoxon p         : 8.5 × 10⁻⁶ (jednostronny, > 0)
permutation P95    : +23 ply

Primary test       : PASS (p < 0.01 AND median ≥ 1.0)
Baseline test      : PASS (median > permutation P95)

Mechaniczny werdykt: HYPOTHESIS SUPPORTED
```

Rozkład wszystkich 35 lagów:
```
+47, +60, +28, +50, +49, +44, +47, +55, -66, +49,
+70, +22, +50, +48, +67,  +9, +25, +69, -48, +73,
+46, +13, +20, +61, +42, +35, +10, +26,  +3, +41,
+43,  -1, +34, +63, +62
```

32 pozytywnych, 3 negatywnych. Sygnał statystycznie istotny.

## 3. Co wyszło naprawdę — analogia samolotów Walda

W II wojnie światowej analitycy patrzyli na samoloty alianckie wracające z misji i mapowali, gdzie są dziury po pociskach. Wniosek brzmiał: „opancerzmy te miejsca, bo tam najczęściej są trafienia". Abraham Wald powiedział: nie. **Trafienia widzicie tylko na samolotach, które wróciły.** Te trafione w silnik nie wróciły, więc nie ma ich w danych. Opancerzcie miejsca, w których nie widzicie trafień — bo to znaczy, że samoloty trafione tam giną.

Mamy dokładnie ten sam problem.

Druga analiza (read-only, z `raw_results_full.json`):

```
FO_ply (gdzie czujnik wykrywa flashover):
  median = 15    (czyli zwykle 15 ruch partii)
  mean   = 19.9
  rozkład: 71% w pierwszych 20 ruchach (debiut)

TP_ply (pierwsza duża dysproporcja w partii):
  median = 58    (zwykle 58 ruch — środkowa gra / endgame)
  mean   = 55.5
```

**Strukturalny shift wynosi 58 − 15 = +43 ruchy.**

Obserwowany lag wynosi +44 ruchy.

**Różnica: +1 ruch.**

To znaczy: nasz czujnik FO pokazuje sygnały głównie w debiucie. Duże dysproporcje TP z definicji zdarzają się w środkowej grze. Lag między nimi byłby ~+43 ruchy **nawet gdyby czujnik FO był kompletnie losowy w pierwszych 20 ruchach**.

Czujnik mierzy gdzie pole drży najmocniej. W debiucie pole drży najmocniej zawsze — bo bierki wychodzą, struktura się buduje, każdy ruch dramatycznie zmienia geometrię. To jest **debiut, nie ActProof**. Tak samo jak „uszkodzenia kabiny i skrzydeł" w danych Walda były **przeżywalnością**, nie słabością.

## 4. Dlaczego permutation baseline tego nie wyłapał

W preregistracji `freeze-v1.4` permutation baseline robił pseudo-FO losowane **uniformly** z [0, długość_partii). Dla średniej długości partii ~80 ruchów, średnie pseudo-FO wynosi ~40. Średnie TP wynosi ~55. Pseudo-lag ~ +15, P95 ~ +23.

Nasz prawdziwy lag = +44 jest powyżej tego P95. **Test baseline'u PASS.**

Ale baseline mówił nam tylko: „obserwowany FO jest *bardziej* skupiony na początku partii niż uniform random". To jest prawda. Ale to nie jest twierdzenie ActProof. To jest właściwość algorytmu `find_peaks` na sygnale `composite |d/dt| z-score` z gradientami brzegowymi.

**Permutation baseline który *naprawdę* testowałby ActProof** losowałby pseudo-FO z tej samej dystrybucji co prawdziwe FO (np. z histogramu empirycznego z silnym pikiem w debiucie). Wtedy pseudo-lag ma medianę ~+43 (strukturalny shift). I dopiero wtedy pytanie: czy obserwowany +44 jest istotnie różny od +43?

Patrząc na rozrzut naszych 35 lagów, odpowiedź najprawdopodobniej: **nie**. Mediany +43 i +44 są w obrębie zwykłego szumu próby tej wielkości.

**Tego stratified baseline'u nie było w preregistracji.** To jest **methodological gap w designie preregistracji**, którego nie zobaczyliśmy aż do drugiej analizy.

## 5. Co to znaczy uczciwie

**Werdykt mechaniczny pod preregistracją:** HYPOTHESIS SUPPORTED. Wszystkie liczby są prawdziwe. Wilcoxon p = 8.5 × 10⁻⁶ jest prawdziwy. Decision matrix dał PASS. Nie naciągamy.

**Werdykt interpretacyjny:** INCONCLUSIVE w mocniejszym sensie. Sygnał statystyczny istnieje, ale jest nieodróżnialny od artefaktu konstrukcji pomiaru. Nie umiemy powiedzieć, czy zmierzyliśmy fragment ActProof signal, czy zmierzyliśmy strukturalny bias czujnika FO do debiutu. Te dwie hipotezy dają w tym konkretnym teście praktycznie nieodróżnialne wyniki.

**Co wiemy z całą pewnością:**
- Liczby są prawdziwe i deterministycznie replikowalne (cache SHA-256, `archive_sha256.txt`).
- Czujnik FO ma silny bias do wczesnych ruchów (≥71% w pierwszych 20 ply).
- Duże dysproporcje TP zdarzają się w klasycznej partii GM zwykle w środkowej grze (mediana 58 ply).
- Te dwa fakty same w sobie wytwarzają strukturalny lag ~+43 ruchy.

**Czego nie wiemy:**
- Czy istnieje *jakikolwiek* ActProof signal nad tym strukturalnym shift.
- Jaki kawałek obserwowanej różnicy +44 vs +43 (czyli +1 ruch) jest sygnałem, a jaki szumem próby.
- Czy inny operacjonalizacja czujnika FO — bez bias do debiutu — dałaby ten sam, inny, czy żaden wynik.

## 6. Lekcje proceduralne

Eksperyment wykonano pod surową preregistracją. W trakcie powstały **cztery ADDENDUMs** — każdy dokumentujący defekt wykryty *przed* zebraniem danych, każdy publicznie commitowany z nowym freeze tagiem:

| ADDENDUM | Defekt | Klasyfikacja |
|----------|--------|--------------|
| 001 | Filter botów sprawdzał błędną konwencję headerów | Implementacja |
| 002 | Dataset (Lichess Elite) strukturalnie nie zawierał klasycznych decisive partii GM | Source change |
| 003 | TWIC server odrzucał default Python-urllib User-Agent (HTTP 406) | Implementacja |
| 004 | Stockfish `no time limit` powodował zawieszenie na patologicznej pozycji | Specification |

Trzy z czterech (001, 003, 004) wynikały z tego, że dostarczany kod był testowany syntaktycznie i import-owo, ale **niesprawdzany operacyjnie** na realnym środowisku. To jest systemowy deficyt po stronie współautora kodu (Claude), uczciwie udokumentowany w treści każdego ADDENDUM.

Smoke testy (v1, v2, v3, v4, v5, v6) wyłapały każdy z tych defektów *przed* skażeniem danych. Koszt: cztery publiczne addendum, kilka cykli iteracji. Korzyść: czysty paper trail i brak naukowego skażenia danych.

**Jednak czwartej lekcji — methodological gap w samym designie permutation baseline'u — nie wyłapał żaden smoke test.** Defekt był w głowie autora preregistracji (Claude), niewidoczny aż do momentu, gdy pełne dane wymagały interpretacji. To pokazuje granicę preregistracji jako narzędzia: chroni przed naciąganiem wyniku po fakcie, ale nie chroni przed brakami w samym designie.

## 7. Co zostaje jako wartość

Pomimo niejednoznacznego werdyktu, eksperyment **wyprodukował konkretne wartości:**

1. **Czujnik ActProof v1.2 jest zaimplementowany, deterministyczny, publicznie dostępny.** Można go uruchomić na dowolnej pozycji szachowej. Mierzy coś — niekoniecznie to, co myśleliśmy, ale coś mierzalnego i replikowalnego.

2. **Pełen paper trail preregistracja → liczby → interpretacja** jest publiczny, datowany, zarchiwizowany w Software Heritage. Każdy może replikować, krytykować, lub zbudować na tej podstawie.

3. **Strukturalny bias czujnika do debiutu** jest twardym, mierzalnym faktem o operacjonalizacji v1.2. Następna iteracja (jeśli powstanie) musi to wziąć pod uwagę.

4. **Lekcja o niewystarczalności permutation baseline'u** jest udokumentowana. To samo w sobie jest naukowo użyteczne: ktokolwiek pracujący nad podobnymi metrykami temporalnymi powinien stratified baseline traktować jako wymaganie, nie opcję.

5. **Czterokrotny pre-data ADDENDUM cycle** jest case study sam w sobie, pokazującym że preregistracja działa nawet w solo research outside academic context — pod warunkiem dyscypliny w wyłapywaniu defektów *przed* danymi.

## 8. Co NIE zostaje (czego eksperyment NIE pokazał)

- **Nie pokazaliśmy**, że ActProof framework jest „potwierdzony", „działający" ani „udowodniony".
- **Nie pokazaliśmy**, że można na podstawie tego czujnika budować narzędzia diagnostyczne dla decyzji ludzkich. Strukturalny confound oznacza, że narzędzie oparte tylko na tym sygnale dawałoby fałszywe wskazania (głównie pokazywałoby "krytyczne momenty" w debiutach, niezależnie od jakości decyzji).
- **Nie pokazaliśmy**, że obserwacja AlphaGo–Lee Sedol move 38 (która zainspirowała cały projekt) była ActProof signal, a nie podobnym artefaktem.

Wynik *nie wyklucza* żadnej z tych rzeczy. Ale ich nie *pokazuje*.

## 9. Następne kroki — opcjonalne

Eksperyment v1.2 jest zamknięty niezależnie od tego, co dalej. Repo `actproof-preflashover` zostaje zarchiwizowany w stanie aktualnym.

Jeśli ActProof ma być rozwijane dalej, sensowne dalsze kierunki:

**(a) Stratified baseline test na tych samych danych.** Read-only, secondary analysis. Sprawdziłoby, czy +44 vs +43 da się odseparować przy rygorystycznym baseline. Nie wymaga nowej preregistracji (pod § 7 explicite dopuszczone jako exploratory). Niski koszt, wysoka informacyjność. **Mogę to zrobić jako następny krok jeśli zechcesz.**

**(b) Nowy eksperyment z innym czujnikiem FO.** Operacjonalizacja, która eliminuje bias do debiutu. Np. czujnik bazowany na strukturze przyszłych możliwości (MultiPV-based), nie na geometrii pola Z/T/S. To jest kierunek, który zarysowałeś w dokumencie roboczym "vNext". **Wymaga nowej preregistracji, nowego repo, nowych danych (TWIC #1525–#1549 lub innych, żeby uniknąć double-dipping).** Nie przed upływem co najmniej tygodnia.

**(c) Replikacja v1.2 na innym datasecie.** Sprawdzenie, czy strukturalny artefakt jest stabilny między różnymi korpusami partii (np. partie Karpova vs Tala, vs amatorzy). Pozytywny test stabilności **wzmocniłby diagnozę artefaktu**, nie ActProof.

(a), (b), (c) są niezależnymi pytaniami. Każde wymaga osobnej decyzji autora projektu.

## 9.5 Secondary Controls — finalna analiza po werdykcie

Po publikacji primary verdict (commit `7760261`, tag `results-v1.0`), wykonano **siedem testów kontrolnych** zaproponowanych przez niezależnych recenzentów (GPT, Claude, Grok) oraz autora (Paweł). Wszystkie testy są **descriptywne i read-only** względem preregistrowanej decision matrix — NIE zmieniają werdyktu mechanicznego.

Pełne wyniki: `SECONDARY_CONTROLS.md`.

### Streszczenie wyników:

| Test | Co testuje | Kluczowy wynik | Wpływ na interpretację |
|---|---|---|---|
| **A** Stratified baseline | Resztkowy sygnał ponad bias FO | +44 ∈ [+33, +46], percentile 90% | Brak resztkowego sygnału |
| **F** Random-game baseline | Czy sensor jest czysto geometryczny | GM median=15, Random=124 (p<10⁻⁸) | Sensor nie czysto geometryczny, ale specyficzny dla teorii debiutowej |
| **C** Non-TP games control | FO niezależne od TP? | GM=15, no-TP=12 (p=0.24 n.s.) | FO odpala niezależnie od istnienia TP |
| **E-temporal** | Stabilność czasowa FO | IQR=12 plies, ρ(FO,length)≈0 | FO jest stałoczasowym zdarzeniem debiutowym |
| **E-spatial** | Per-piece field decomposition | **98% energii pola = król** | Sensor mechanicznie zmuszony do skupienia na królu |
| **B-correlation** | Lag jako artefakt długości | ρ(lag,length)=0.28 (p=0.10 n.s.) | Lag nie jest artefaktem długości partii |
| **B-permutation** | Phase-matched baseline 1000× | Baseline median=+44 (dokładnie) | Zero resztkowego sygnału w bucket-level |

### Werdykt interpretacyjny — zmiana z INCONCLUSIVE na DISPROVED

Po siedmiu testach kontrolnych zmiana interpretacji:

- **Werdykt mechaniczny** (per preregistrowana decision matrix): **HYPOTHESIS SUPPORTED** — bez zmian. Liczby są prawdziwe, decision matrix zaaplikowany mechanicznie.
- **Werdykt interpretacyjny** (per secondary controls): **DISPROVED** — operacjonalizacja czujnika v1.2 nie wykrywa pre-flashover w sensie zamierzonym przez H1.

### Konkretny mechanizm confoundu (z Testu E-spatial)

Test E-spatial dostarczył **konkretnego dowodu mechanizmu** strukturalnego confoundu:

Pole Z(x,y) liczone jako `1/r` Coulomb-like z masami {P:1, N:3, B:3, R:5, Q:9, K:100} jest **w 98% zdominowane przez energię wokół króla**. Wszystkie pozostałe figury razem stanowią mniej niż 2% energii pola.

To znaczy:
- Masa króla=100 vs pozostałe masy=1-9 daje ratio 11:1 niezależnie od dystansu r.
- Czujnik **mechanicznie zmuszony** jest mierzyć aktywność wokół króla.
- "Top-1 flashover" to w 98% **wydarzenia związane z królem** (roszada, ruchy przygotowawcze, zmiana otoczenia).
- Debiut zawiera intensywne ruchy wokół króla → FO konsekwentnie odpala wczesne (median 15).

**ActProof v1.2 nie jest "detektorem decyzji szachowej". Jest detektorem aktywności wokół króla w debiucie.**

### Cztery niezależne testy konwergują na tej samej diagnozie:

1. **Test A:** Stratified baseline z empirycznej dystrybucji FO_ply → median baseline = +41, obserwowany +44 w 95% CI.
2. **Test B-permutation:** Phase-matched baseline → median baseline = +44.0 (dokładnie), obserwowany +44 dokładnie na medianie.
3. **Test C:** Non-TP games → FO_ply identyczne z TP-games (jeśli sensor "wiedział" o nadchodzącym TP, no-TP games powinny mieć inne FO).
4. **Test E-temporal:** FO_ply nie koreluje z game length ani TP_ply → stałoczasowe zdarzenie debiutowe, nie predyktor.

Konwergencja czterech niezależnych metod na tej samej diagnozie jest **statystycznie i metodologicznie robustna**.

### Konstrukcyjne wady operacjonalizacji v1.2

Z analizy mechanizmu confoundu wynikają trzy konkretne problemy konstrukcyjne:

1. **Mass scaling figur:** Król=100 vs pozostałe (1-9) daje mechaniczną dominację. Każda przyszła iteracja musi rozważyć alternatywne skalowanie (np. równe masy, masy nieliniowe, masy zależne od pozycji).

2. **Field decay function:** `1/r` decay daje globalną dominację dużych mas. Lokalne metryki (krótszy decay, lokalne kernels) mogłyby umożliwić mierzenie figur o niskiej masie.

3. **Peak detection:** `find_peaks` z `prominence=0.8` na composite z-score wybiera **pierwszy główny gradient**, który w GM games jest zawsze przejściem debiutowym. Inne strategie (last significant peak, weighted average peak, pre-TP-window peak) mogłyby dać inne wyniki.

### Co eksperyment NIE pokazał

- **Nie pokazał**, że framework ActProof jako całość jest obalony. Testowano jedną konkretną operacjonalizację.
- **Nie pokazał**, że hipoteza o pre-flashover signal jest niemożliwa. Pokazał że ta operacjonalizacja nie jest właściwym narzędziem.
- **Nie pokazał**, że obserwacja AlphaGo–Lee Sedol Game 2 (ruch 37/38) jest artefaktem. Inne metody (KataGo delta_stability) wskazują na ten moment — nasza operacjonalizacja po prostu nie miała narzędzia do jego wykrycia.

### Co eksperyment pokazał z pewnością

- **Operacjonalizacja v1.2 jest martwa** dla testowania pre-flashover detection w obecnej formie.
- **Konkretny mechanizm confoundu** zidentyfikowany (98% pole = król, ze masy 100).
- **Trzy konkretne lekcje** dla przyszłych eksperymentów ActProof:
  1. Permutation baseline musi kontrolować strukturalny bias czujnika.
  2. Fizyczna analogia nie zastępuje domenowej struktury.
  3. Pozytywny wynik mechaniczny z confoundem strukturalnym jest gorszy niż jasny negatywny wynik.

### Wpływ na repo

Status repo po tej sekcji: **PENDING_FINAL_REVIEW** — czeka na review przez Pawła przed:
- Tag `results-v1.1-final`
- Software Heritage save post-results
- `gh repo archive`

Po archiwizacji repo staje się read-only, cytowalne, immutable — z kompletnym paper trail od preregistracji przez cztery ADDENDUM-y do siedmiu secondary controls.

## 10. Osobista nota od autora

Nie jestem naukowcem w sensie instytucjonalnym. Nie mam tytułu, uczelni, publikacji peer-reviewed. Projekt prowadziłem solo, z asystą czterech modeli AI (z którymi konsultowałem różne fragmenty) i jednego asystenta operacyjnego (DEP).

Ten raport nie jest publikacją naukową. Jest **uczciwym dokumentem inżynierskim** opisującym, co zrobiliśmy, co wyszło, co to znaczy i co tego nie znaczy. Ma chronić wszystkich — w tym mnie samego — przed budowaniem narzędzi na fundamencie, który okazał się słabszy niż początkowo wyglądał.

Ważniejsze niż wynik tego konkretnego testu są dwie rzeczy:

1. **Procedura zadziałała.** Cztery defekty wykryte przed danymi, jeden defekt wykryty w drugiej analizie, każdy publicznie udokumentowany. Żadna liczba w tym raporcie nie jest naciągnięta. Decision matrix był wymalowany w kamieniu przed zobaczeniem danych i został zastosowany mechanicznie.

2. **Wynik niejednoznaczny jest wynikiem.** Większość rzeczywistych eksperymentów naukowych kończy się "inconclusive" albo "negative". Nie wszystko, co się testuje, działa. To jest normalne. To jest informatywne. To nie jest porażka.

Trzy dni intensywnej pracy dały jeden niejednoznaczny wynik i bardzo konkretny next step. Następna iteracja — jeśli powstanie — będzie lepsza, bo widziała, gdzie pierwsza zawiodła.

To wystarczy.

---

## Pliki w tym repozytorium

| Plik | Cel |
|------|-----|
| `PREREGISTRATION.md` | Historyczny (v1.0/v1.1). Superseded. |
| `PREREGISTRATION-v1.2.md` | Historyczny (v1.2/v1.3). Superseded. |
| `PREREGISTRATION-v1.4.md` | **Authoritative** preregistracja użyta dla finalnego runu. |
| `ADDENDUM-001.md` … `ADDENDUM-004.md` | Public addendums dokumentujące cztery pre-data defekty. |
| `actproof_chess.py`, `actproof_dynamics.py` | Czujnik ActProof. Niezmienne od `freeze-v1.0`. |
| `data_collection.py` | Pipeline ewaluacyjny. Aktualny stan: `freeze-v1.4`. |
| `requirements.txt` | Zależności runtime z pinned versions. |
| `results/analysis_full.json` | Mechaniczny werdykt z liczbami statystycznymi. |
| `results/raw_results_full.json` | Per-partia: TP, FO, lag, exclusion reason. |
| `results/full_run.log` | Pełny stdout pipeline'u. |
| `results/archive_sha256.txt` | Deterministyczny anchor datasetu TWIC. |
| `results/diagnostic_breakdown.log` | Evidence dla ADDENDUM-002. |
| `REPORT.md` | Ten dokument. |
| `SECONDARY_CONTROLS.md` | Siedem kontroli wtórnych (A, F, C, E-temporal, E-spatial, B-correlation, B-permutation). |
| `STATUS.md` | Status repozytorium. |
| `secondary_controls_helpers.py` | Helper do Testu A (stratified permutation). |
| `test_b_lag_length.py` | Test B-correlation. |
| `test_b_permutation.py` | Test B-permutation (phase-matched). |
| `test_c_notp_fo.py` | Test C (non-TP games FO). |
| `test_e_per_piece.py` | Test E-temporal (timing correlations). |
| `test_e_spatial.py` | Test E-spatial (per-piece decomposition). |
| `test_f_random_baseline.py` | Test F (random-game baseline). |

## Replikacja

```bash
git clone https://github.com/pawelsokaris-sudo/actproof-preflashover.git
cd actproof-preflashover
git checkout freeze-v1.4
pip install -r requirements.txt
# Pobierz Stockfish 16+ z https://stockfishchess.org/download/
python data_collection.py --full --stockfish /path/to/stockfish
# Wyniki powinny być bit-identyczne z plikami w results/
# (Stockfish jest deterministyczny przy Threads=1, depth=22)
```

## Licencja

Kod: MIT. Dokumenty (preregistracja, addendums, raport): CC-BY-4.0.

Pełna swoboda używania, modyfikowania, replikacji, krytyki. Jedyne wymaganie: zachowanie atrybucji i udokumentowanie modyfikacji.

---

*„Wartość tego, co zrobiliśmy, nie polega na tym, że potwierdziliśmy hipotezę. Polega na tym, że mamy teraz kompletny, datowany, publiczny ślad — jak myśleliśmy, co testowaliśmy, co znaleźliśmy, jak to interpretowaliśmy, gdzie się myliliśmy. To jest dokument, na którym ktoś następny może zbudować coś lepszego, bez powtarzania naszych pułapek."*
