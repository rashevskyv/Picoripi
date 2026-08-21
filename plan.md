# План розробки: Вдосконалення діалогу Merge Speakers

- [x] 1. Додати чекбокси та швидкий фільтр/пошук у дерево Merge Speakers ([components/speaker_merge_dialog.py](file:///D:/git/dev/Picoripi/components/speaker_merge_dialog.py)).
- [x] 2. Створити інтерактивну панель вибору кандидатів у правому інспекторі:
  - Кнопки для окремих кандидатів (`[ HANCH ]`, `[ MALO ]`, `[ TALO ]`).
  - Окремі кандидати та очищення (`[ Clear ]`); конфлікт не зберігається як фіктивне складене ім'я.
  - Поле введення імені з живою синхронізацією з деревом.
  - Кнопка негайного застосування одного спікера (`[ Apply This Speaker ]`).
- [x] 3. Додати контекстне меню дерева для швидких дій над рядками.
- [x] 4. Оновити нижню панель: чіткі кнопки `Apply Checked (N)`, `Apply All Valid`, `Close` та динамічний лічильник.
- [x] 5. Написати паралельні тести для всіх нових можливостей ([tests/test_components/test_speaker_merge_dialog.py](file:///D:/git/dev/Picoripi/tests/test_components/test_speaker_merge_dialog.py)).
- [x] 6. Оновити документацію, changelog та ітерувати версію.
