# QuickView

macOS Quick Look для KDE Plasma 6 / Dolphin.

Нажми пробел (или правый клик → Quick View) — мгновенный предпросмотр файла без его открытия.


## Что умеет

| Тип файла | Что показывает |
|---|---|
| Изображения (jpg, png, webp, gif…) | Масштабируемый предпросмотр |
| PDF | Первая страница |
| Видео (mp4, mkv, avi…) | Миниатюра + плеер с управлением |
| Аудио (mp3, flac, ogg…) | Плеер с управлением и слайдером |
| Текст / код (py, js, rs, c…) | Подсветка синтаксиса (monokai) |
| HTML | Рендер страницы через WebEngine |
| Архивы (zip, tar, gz, bz2…) | Список файлов внутри |
| Папки | Список содержимого |
| Всё остальное | Имя, тип, размер |

**Интерфейс:** полупрозрачное размытое окно, динамически подстраивается под размер содержимого, центрируется на экране, перетаскивается за заголовок.

## Установка

### Быстро (Arch / CachyOS / Manjaro)

```bash
git clone https://github.com/LexYena/ArchQuickView
cd quickview
bash install.sh
```

Скрипт установит все зависимости через `pacman` и настроит сервисное меню Dolphin.

После установки — **перезапусти Dolphin**.

### Через makepkg (как пакет Arch)

```bash
cd quickview
makepkg -si
```

### Вручную

1. Установи зависимости:

```bash
sudo pacman -S --needed \
    python-pyqt6 python-pyqt6-webengine \
    poppler ffmpegthumbnailer ffmpeg \
    python-pillow python-pygments

# Для воспроизведения видео/аудио (опционально):
sudo pacman -S python-mpv   # или: yay -S python-mpv
```

2. Скопируй скрипт:

```bash
cp quickview.py ~/.local/bin/quickview
chmod +x ~/.local/bin/quickview
```

3. Установи сервисное меню Dolphin:

```bash
mkdir -p ~/.local/share/kio/servicemenus
cp quickview.desktop ~/.local/share/kio/servicemenus/
# Отредактируй путь в Exec= если нужно
```

4. Перезапусти Dolphin.

## Использование

**Из Dolphin:**
- Правый клик на файле → **Quick View**

**Из терминала:**
```bash
quickview /path/to/file
quickview /path/to/directory
```

**Управление окном:**
- `Esc` — закрыть
- Перетаскивание за заголовок — переместить окно

## Зависимости

| Пакет | Для чего | Обязательно |
|---|---|---|
| `python-pyqt6` | GUI | да |
| `python-pyqt6-webengine` | Рендер HTML | да |
| `poppler` | Предпросмотр PDF (`pdftoppm`) | рекомендуется |
| `ffmpegthumbnailer` | Миниатюры видео | рекомендуется |
| `ffmpeg` | Размеры видео (`ffprobe`) | рекомендуется |
| `python-pillow` | Быстрое чтение размеров изображений | рекомендуется |
| `python-pygments` | Подсветка синтаксиса кода | рекомендуется |
| `python-mpv` | Воспроизведение видео и аудио | опционально |

Всё кроме `python-mpv` есть в официальных репозиториях Arch. `python-mpv` — в AUR.

## Требования к системе

- KDE Plasma 6
- Dolphin
- Python 3.11+
- Wayland или X11

## Почему не klook / sushi?

- **klook** — заброшен 6+ лет, не работает с KDE 6
- **sushi** — только для GNOME / Nautilus
- **Gwenview** — только изображения, нет интеграции как Quick Look
