# OWNERS — статистика летней лиги

Интерактивный дашборд второй команды Лео: турнир **REST ROFL** (лига ABL, дивизион ниже Akatsuki).
Близнец дашборда [akatsuki-stats](https://github.com/Leocryptus/akatsuki-stats), палитра — «Vice City».

**Live:** https://leocryptus.github.io/owners-stats/

## Как обновить после игры

```bash
cd ~/brain/owners
python3 build.py            # тянет API mtgame.ru → data.json + data.js, качает фото новичков
git add -A && git commit -m "game <gid>: Owners <счёт> <соперник>" && git push
```

Через пару минут GitHub Pages подхватит. Вручную ничего вбивать не надо — как только матч
получает статус `closed` в турнире, он появляется сам.

## Данные

Публичный API `https://mtgame.ru/api/v1`:

| что | эндпоинт |
|---|---|
| игры турнира | `tournament/4025/games/` |
| карточка матча | `tournament_basketball_game/{gid}/` |
| статистика игроков | `tournament_basketball_game/{gid}/user_statistic/` |
| командные тоталы | `tournament_basketball_game/{gid}/team_statistic/` |
| ростер на матч | `tournament_game/{gid}/users/` |

ID: турнир **4025** (REST ROFL), Owners `team_id` **10697**, `tournament_team_id` **30796**.
Owners бывает и `team`, и `competitor` — сторона определяется по `team_id`.
Агрегация по `user.id` (номера у игроков плавают между матчами).

## Что внутри

- **Команда** — рекорд, форма, средние за игру, график забито/пропущено, реализация,
  лучшая пятёрка, power ranking, лидеры сезона.
- **Игроки** — карточка на каждого: амплуа + NBA-компаратив, индекс формы, личные рекорды,
  график очков по играм, полный протокол.
- **Игры** — счёт по четвертям, командные цифры, бокс-скор матча.

Сайт закрыт от индексации (`noindex` + `robots.txt`).
