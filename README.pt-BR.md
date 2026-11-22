[English](README.md) | Português (Brasil)

# Terrascope

[![CI](https://github.com/a-shygun/Terrascope/actions/workflows/ci.yml/badge.svg)](https://github.com/a-shygun/Terrascope/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/Terrascope)](https://pypi.org/project/Terrascope/)
[![Python](https://img.shields.io/pypi/pyversions/Terrascope)](https://pypi.org/project/Terrascope/)
[![License](https://img.shields.io/github/license/a-shygun/Terrascope)](LICENSE)

![Demonstração animada da interface do Terrascope](docs/images/terrascope-ui-promo.gif)

O `terrascope` é um mapa-múndi interativo para o terminal. Ele desenha países,
nomes de lugares, aeronaves ao vivo, o clima das cidades, uma camada de radar,
sismos e as faixas de dia e noite com `curses`, células Braille do Unicode e as
cores do terminal.

O app é propositalmente leve na instalação. Os dados grandes do mapa são
baixados para um cache do usuário na primeira vez em que são necessários e
reutilizados nas execuções seguintes.

Os nomes e as siglas dos países, além dos nomes e das posições dos aeroportos,
vêm embutidos a partir do Natural Earth, de modo que ficam disponíveis offline
sem um download na primeira execução.

## Situação

Este projeto é um software em estágio inicial. O mapa principal, as abas, a
navegação por teclado e mouse, as camadas ao vivo e o tratamento do cache já
estão implementados, mas as APIs e os detalhes visuais ainda podem mudar.

## Requisitos

- Python 3.10 ou mais recente no macOS, Linux/Unix ou Windows 10/11
- Um terminal UTF-8 (no Windows: Windows Terminal ou o console clássico)
- Um terminal com suporte a 256 cores ou true color, para a melhor aparência
- Acesso à rede para os downloads do mapa na primeira execução e para as camadas de dados ao vivo (opcional)

As dependências Python estão declaradas no `pyproject.toml`:

- `numpy`
- `Pillow`
- `PyYAML`
- `pyshp`
- `windows-curses` e `tzdata` (somente no Windows, instalados automaticamente)

## Instalação

Para a versão publicada mais recente:

```bash
pipx install terrascope
terrascope
```

### Gerenciadores de pacotes

O Homebrew pode instalar a versão marcada mais recente ou o código mais recente da `main`:

```bash
# Homebrew, latest published release
brew tap a-shygun/terrascope https://github.com/a-shygun/Terrascope.git
brew install a-shygun/terrascope/terrascope

# Homebrew, latest code on main before the next tagged release
brew install --HEAD a-shygun/terrascope/terrascope

# pipx, latest code on main before the next tagged release
pipx install --force "git+https://github.com/a-shygun/Terrascope.git@main"

# Nix, from a Terrascope checkout (uses that checkout's source and version)
nix run ./packaging/nix

# Arch Linux, stable release from the AUR
yay -S terrascope

# Arch Linux, latest code on main from the AUR
yay -S terrascope-git
```

O PyPI e a instalação padrão do Homebrew usam as versões marcadas com tag. A
versão delas vem do `pyproject.toml`; a fórmula do Homebrew a lê diretamente. O
pacote `terrascope` do AUR acompanha as versões marcadas, enquanto o
`terrascope-git` acompanha a `main`. A opção `--HEAD` do Homebrew, a instalação
do pipx a partir do repositório e a receita do Nix para um checkout usam o
código atual da `main`.

### Downloads para Linux (.deb, .rpm, AppImage, tarball)

Cada GitHub Release marcada com tag anexa builds independentes para
`linux_x86_64` e `linux_arm64` (além de tarballs para macOS). Escolha os
arquivos que correspondem à sua máquina na
[página de Releases](https://github.com/a-shygun/Terrascope/releases):

```bash
VERSION=1.0.0
ARCH=linux_x86_64  # or linux_arm64

# Debian / Ubuntu
sudo apt install ./terrascope_${VERSION}_${ARCH}.deb

# Fedora / RHEL / openSUSE
sudo dnf install ./terrascope_${VERSION}_${ARCH}.rpm
# or: sudo rpm -i ./terrascope_${VERSION}_${ARCH}.rpm
# or on openSUSE: sudo zypper install ./terrascope_${VERSION}_${ARCH}.rpm

# AppImage (no root needed)
chmod +x ./terrascope_${VERSION}_${ARCH}.AppImage
./terrascope_${VERSION}_${ARCH}.AppImage

# Portable tarball
tar -xzf ./terrascope_${VERSION}_${ARCH}.tar.gz
./terrascope --help
```

Os builds `.deb`, `.rpm` e `.tar.gz` trazem todos o mesmo binário PyInstaller
`terrascope`, instalado como `/usr/bin/terrascope` (`.deb`/`.rpm`) ou como
`./terrascope` (tarball). O AppImage empacota o mesmo binário com sua entrada de
desktop e seu ícone, então roda sem instalação. As somas de verificação SHA-256
de todos os arquivos são publicadas em `terrascope_checksums.txt`, junto dos
arquivos da release.

### Windows

O `pipx install terrascope` funciona no Windows como nas outras plataformas; as
dependências exclusivas do Windows (`windows-curses`, `tzdata`) são instaladas
automaticamente. As versões marcadas também anexam um build independente, que
dispensa o Python:

```powershell
# Scoop, straight from the release manifest
scoop install https://github.com/a-shygun/Terrascope/releases/latest/download/terrascope.json

# winget (once the package is published in winget-pkgs)
winget install AShygun.Terrascope

# Portable zip: terrascope_<version>_windows_x86_64.zip from the Releases page
Expand-Archive .\terrascope_1.0.0_windows_x86_64.zip -DestinationPath .\terrascope
.\terrascope\terrascope.exe --help
```

O Windows Terminal dá o melhor resultado; o console clássico também funciona.
Use uma fonte com glifos Braille, como a Cascadia Mono (a padrão do Windows
Terminal).

Para desenvolvimento local:

```bash
git clone https://github.com/a-shygun/terrascope.git
cd terrascope
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
terrascope
```

Também é possível rodar a partir de um checkout sem instalar o script de console:

```bash
PYTHONPATH=src python3 -m terrascope
```

## Primeira execução e cache

Na primeira execução, o `terrascope` baixa arquivos GeoJSON do Natural Earth para:

```text
$XDG_CACHE_HOME/terrascope
```

Se `XDG_CACHE_HOME` não estiver definida, o padrão é:

```text
~/.cache/terrascope
```

Comandos úteis para o cache:

```bash
terrascope --show-paths
terrascope --clear-cache
terrascope --offline
```

## Opções comuns

```bash
terrascope --help                         # all options and defaults
terrascope --tab weather --offline        # open a tab using cached data only
terrascope --panel-orientation vertical   # put the panel in a left sidebar
terrascope --no-radar --no-airports       # disable optional overlays
terrascope --disable-layer night          # start with a layer disabled
terrascope --config ~/terrascope.yaml     # load additional settings
terrascope --set 'map.zoom.max=128'       # override one setting for this run
terrascope --show-paths                   # show cache and config locations
terrascope --clear-cache                  # remove cached downloads and API data
terrascope --dump-config                  # print effective settings
terrascope --list-keys                    # show active keyboard shortcuts
```

As opções da linha de comando substituem a configuração na execução atual. O
`--set` substitui as opções; veja `terrascope --help` para a ordem de
precedência completa e todas as opções disponíveis.

Durante os downloads da primeira execução, a interface do terminal mostra uma
mensagem de carregamento antes de o mapa aparecer. Erros e avisos de segundo
plano são gravados no arquivo de log mostrado por `terrascope --show-paths`, para
que nenhuma saída solta corrompa a tela do curses.

## Controles

| Entrada | Ação |
| --- | --- |
| `1`-`9` | Trocar de aba |
| `WASD` ou setas | Mover o mapa |
| `+` / `-` | Aproximar / afastar |
| `0` | Redefinir a vista |
| Arrastar com o mouse | Mover o mapa |
| Roda do mouse | Zoom |
| Clique do mouse | Selecionar um marcador ou rótulo do mapa |
| `<` / `>` | Percorrer seleções sobrepostas |
| `/` | Buscar |
| `O` | Abrir o campo de filtro |
| `H` | Mostrar ou ocultar o painel |
| `?` | Abrir a janela de boas-vindas/ajuda |
| `Esc` | Fechar campos ou limpar a seleção/o filtro |
| `Q` | Sair |

Clique em `[+]` ao lado do relógio para expandir os controles do topo e depois
clique no rótulo da posição do painel (`BOTTOM` ou `LEFT`; em pt-BR, `BAIXO` ou
`ESQUERDA`) para alternar o painel entre a linha horizontal embaixo e a barra
lateral vertical à esquerda. O padrão é vertical;
`--panel-orientation vertical` ou `--panel-orientation horizontal` escolhe o
layout inicial de uma execução. `--set ui.panel_orientation=vertical` também
funciona. No painel vertical de clima, role sobre a previsão para percorrer o
detalhe completo de cada dia, incluindo o gráfico de temperatura, as condições,
a precipitação, o vento e o nascer/pôr do sol.

Teclas específicas das camadas:

| Tecla | Camada |
| --- | --- |
| `P` | Voos |
| `K` | Aeroportos na aba de voos |
| `C` | Rótulos de clima das cidades |
| `E` | Sismos |
| `N` | Camada de dia/noite |
| `L` | Modo de tinta/preenchimento do dia/noite |
| `[` / `]` | Deslizador de tempo, onde houver |
| `Z` | Abre o seletor de fuso horário na aba HORA; digite para buscar, use as setas para navegar e pressione Enter para selecionar |

Rode este comando para ver a lista de teclas em vigor:

```bash
terrascope --list-keys
```

## Abas e camadas

- `MAP` (`MAPA`): mapa-múndi base, com detalhes de países, províncias/estados e
  cidades conforme o zoom permite.
- `TIME` (`HORA`): faixas de dia e noite, informações do sol e da lua e seleção
  de fuso horário. Pressione `Z` (indicado ao lado do relógio) para abrir o
  seletor de fuso horário sem mouse; digite o nome de um fuso para buscar,
  navegue com as setas, selecione com Enter ou feche com Esc.
- `WEATHER` (`CLIMA`): clima das cidades, painel de previsão, camada de radar e
  sismos do USGS.
- `PLANES` (`VOOS`): posições das aeronaves do OpenSky, rastros, categorias e
  marcadores de aeroportos do Natural Earth.

## Como escrever um plugin

Um pacote Python separado pode adicionar camadas ao mapa e abas à linha do topo
sem alterar o Terrascope. Registre-as em dois grupos de entry points:

- `terrascope.layers`: cada entrada aponta para uma subclasse de
  `terrascope.core.layer.Layer`.
- `terrascope.tabs`: cada entrada aponta para uma função que retorna uma lista
  de dicts no mesmo formato de `tabs.items` em `default.yaml` (`name`, `label`,
  `color` e, opcionalmente, `blurb`, `layers`, `attribution`, `view`, ...).
  O `label` e o `blurb` passam pela tradução do Terrascope (`_()`), então uma
  mensagem que o catálogo do core conhece aparece no idioma do usuário.
  Traduza os seus próprios textos com o catálogo do seu pacote (veja
  `translation()` em `terrascope.core.i18n`); o core não conhece os msgids deles.

O `view` opcional define a vista inicial da aba: `view: {lat: -14, lon: -52, zoom: 3}`.
O Terrascope move o mapa para lá quando a aba é aberta, com o centro indicado
(`lat` entre `map.lat_min` e `map.lat_max`, as latitudes que o mapa mostra;
`lon` de -180 a 180) e o `zoom` (entre `map.zoom.min` e `map.zoom.max`, ou o
`zoom_max` da aba).
Abrir a mesma aba de novo não move o mapa. Sem `view`, a aba mantém a vista que
o usuário tinha. A tecla `0` volta para a vista da aba quando ela tem uma, e
para o mundo inteiro caso contrário. Uma aba embutida com um `view` inválido
interrompe o app na inicialização, informando o motivo; uma aba de plugin com
um `view` inválido é ignorada com um aviso.

O `zoom_max` opcional é o nível de maior aproximação enquanto a aba está ativa,
no lugar de `map.zoom.max` (de `map.zoom.min` até 1024). Uma aba regional pode
deixar o usuário chegar bem mais perto do que o mapa-múndi permite:
`zoom_max: 256` mostra cerca de 0,55 grau de latitude. Ao sair da aba, o mapa
se afasta até o limite da outra aba, quando necessário. A partir de
`map.zoom.detail_min` (16), as costas e as fronteiras dos países vêm de
`data.countries_detail_file` (Natural Earth 1:10m), baixado em segundo plano na
primeira vez em que a vista chega lá (cerca de 13 MB; defina
`data.countries_detail_file: ""` para manter os contornos 1:50m em todos os
zooms). Um download que falhou é tentado de novo depois de um minuto.

Uma aba de plugin precisa ter `name`, `label` e `color` (`#rrggbb`); `blurb` e
`attribution` são textos, `layers` é uma lista de nomes de camadas, e
`detailed`, `provinces`, `place_names` e `country_names` são verdadeiro ou
falso. Chaves desconhecidas são um erro. O nome de uma aba é comparado sem
diferenciar maiúsculas e minúsculas e não pode conter só dígitos (os dígitos
selecionam uma aba pelo número). Uma aba de plugin que desrespeita essas regras
é ignorada com um aviso, e o app inicia sem ela.

- `terrascope.weather_providers`: cada entrada aponta para uma função que
  retorna uma lista de instâncias de `WeatherProvider`
  (`terrascope.layers.weather.providers`). Um provedor tem um `name` (mostrado
  como FONTE na caixa de informações e depois da cidade no título da previsão)
  e uma `priority`, e implementa `covers(latitude, longitude)` e
  `fetch(latitude, longitude)`, que retorna um `WeatherReading` com as
  condições atuais, os dias de previsão ou ambos, e lança `WeatherFetchError`
  quando a fonte falha. Para cada cidade, os provedores que a cobrem são
  consultados da maior prioridade para a menor, e cada parte vem do primeiro
  que a tiver; o Open-Meteo embutido cobre todos os lugares e é consultado por
  último. Assim, uma fonte regional pode fornecer a previsão da sua área
  enquanto o Open-Meteo continua fornecendo as condições do momento. Os dois
  métodos rodam em uma thread de segundo plano. Um entry point com defeito é
  ignorado com um aviso.

```toml
# pyproject.toml of the plugin package
[project]
name = "terrascope-demo"
version = "0.1.0"
dependencies = ["terrascope"]

[project.entry-points."terrascope.layers"]
demo = "terrascope_demo.layers:DemoLayer"

[project.entry-points."terrascope.tabs"]
demo = "terrascope_demo.tabs:demo_tabs"
```

```python
# terrascope_demo/layers.py
from terrascope.core.layer import Layer, LayerRender, Marker


class DemoLayer(Layer):
    name = "demo"        # unique: used by --disable-layer and by tab "layers"
    toggle_key = "j"     # a key that neither the app nor a built-in layer uses (see below)

    def build(self, view) -> LayerRender:
        markers = []
        cell = view.to_cell(0.0, 51.5)  # longitude, latitude
        if cell is not None:
            markers.append(Marker(cell[0], cell[1], "#ff0000", glyph="o", label="London"))
        return LayerRender(None, "#000000", markers=markers)
```

```python
# terrascope_demo/tabs.py
def demo_tabs():
    return [
        {
            "name": "demo",
            "label": "DEMO",
            "color": "#ff00ff",
            "blurb": "a marker over London",
            "layers": ["basemap", "demo"],   # Layer.name values switched on
            "attribution": "Example data",
        }
    ]
```

Um plugin que desenha texto esmaecido deve usar `DIM_ATTR` de
`terrascope.core.ui.constants` em vez de `curses.A_DIM`. No Windows, o PDCurses
não tem atributo de esmaecimento, então lá `curses.A_DIM` vale 0, e o
`DIM_ATTR` usa `curses.A_BLINK` no lugar. Para um Terrascope que ainda não o
tem:

```python
try:
    from terrascope.core.ui.constants import DIM_ATTR
except ImportError:
    import curses
    DIM_ATTR = curses.A_DIM
```

Instale o pacote no mesmo ambiente do Terrascope (`pip install -e .`) e depois
rode `terrascope --list-layers` e `terrascope --list-tabs`: a última coluna
mostra `plugin:terrascope-demo` para as novas entradas. Desinstalar o pacote as
remove.

Um plugin que falha ao carregar, não é uma subclasse de `Layer` ou não consegue
ser iniciado é ignorado com um aviso, e o app inicia sem ele. Uma camada de
plugin também é ignorada com um aviso quando sua tecla de alternância não é um
único caractere ASCII visível (um número, ou `"jk"`, por exemplo), ou quando a
tecla já está em uso: pelo app, por uma camada embutida ou por uma camada de
plugin adicionada antes dela. As teclas que o app usa são os dígitos, as teclas
de `app.keys` em `default.yaml` (por exemplo `q`, `h`, `o`, `w`, `a`, `s`,
`d`, `z`, `0`, `+`, `-`), `r`, `x`, `y`, `n` e as teclas das camadas embutidas
(`toggle_key` e `look_key` em `layers:`: `k` aeroportos, `c` cidades, `e`
sismos, `l` aparência do dia/noite). Duas camadas embutidas com a mesma tecla
continuam interrompendo o app com um erro. Escolha uma letra que nenhuma delas
use e confira a lista com `terrascope --list-keys` e `--list-layers`.
As camadas de plugin são desenhadas por cima das embutidas, na ordem em que os
seus entry points são encontrados.

## Capturas de tela

### Mapa

![Vista global do mapa](docs/images/map-global.png)

*Vista global do mapa.*

![Mapa da Europa de perto, sem as divisas das províncias](docs/images/map-eu-close-up-no-province.png)

*Europa de perto, sem as divisas das províncias.*

![Mapa da Europa de perto, com as divisas das províncias](docs/images/map-eu-close-up-with-province.png)

*Europa de perto, com as divisas das províncias.*

### Hora

![Vista global da aba HORA com preenchimento de dia e noite](docs/images/time-global-fill.png)

*Vista global com preenchimento de dia e noite.*

![Vista global da aba HORA com tinta de dia e noite](docs/images/time-global-tint.png)

*Vista global com tinta de dia e noite.*

![Vista global da aba HORA com preenchimento e sem painel](docs/images/time-global-fill-no-panel.png)

*Vista global com preenchimento e o painel oculto.*

![Aba HORA com o painel na horizontal](docs/images/time-horizontal-layout.png)

*Aba HORA com o painel na horizontal.*

### Clima

![Vista global do clima com o painel vertical](docs/images/weather-global-vertical.png)

*Vista global do clima com o painel vertical.*

![Vista global do clima sem painel](docs/images/weather-global-no-panel.png)

*Vista global do clima com o painel oculto.*

![Clima da Europa de perto, com radar](docs/images/weather-eu-radar-close-up.png)

*Europa de perto, com a camada de radar.*

![Aba CLIMA com o painel na horizontal](docs/images/weather-horizontal-layout.png)

*Aba CLIMA com o painel na horizontal.*

### Voos

![Vista global dos voos](docs/images/planes-global.png)

*Vista global das aeronaves.*

![Voos de perto sobre o Reino Unido](docs/images/planes-uk-close-up.png)

*Aeronaves de perto sobre o Reino Unido.*

## Configuração

Os valores padrão ficam em:

```text
~/.config/terrascope/default.yaml
```

Na primeira execução, o Terrascope copia os padrões embutidos para esse local e
carrega essa cópia, que pertence ao usuário. Arquivos existentes são mantidos
entre atualizações. Se `XDG_CONFIG_HOME` estiver definida, o Terrascope usa
`$XDG_CONFIG_HOME/terrascope/default.yaml`.

É possível substituir configurações sem editar o pacote:

```bash
terrascope --config ~/terrascope.yaml
terrascope --set 'map.zoom.max=128'
terrascope --set 'map.land_color="#101018"'
terrascope --set 'app.keys.timezone="t"'
```

O atalho do seletor de fuso horário é `Z` por padrão e funciona na aba HORA.
Defina `app.keys.timezone` na sua configuração com outro caractere ou uma lista
de caracteres se preferir outra tecla. `terrascope --list-keys` mostra o atalho
em vigor.

Para inspecionar a configuração final combinada:

```bash
terrascope --dump-config
```

No Windows, cujo console não tem atributo de esmaecimento, o texto esmaecido
(abas inativas, dicas) é desenhado com uma cor mais escura. O console não
informa a sua cor de fundo, então por padrão a cor esmaecida tende ao preto. Em
um terminal claro, defina `terminal.background: light` (ou `--background light`)
para que o texto esmaecido tenda ao branco e continue legível.
Os terminais do Linux e do macOS desenham o texto esmaecido por conta própria,
então lá a configuração não tem efeito.

Variáveis de ambiente importantes:

| Variável | Significado |
| --- | --- |
| `terrascope_OFFLINE=1` | Desativa as requisições de rede ao vivo |
| `terrascope_CONFIG=/path/file.yaml` | Carrega um arquivo de configuração antes das opções da linha de comando |
| `terrascope_RAINVIEWER_URL=https://...` | Substitui a API de catálogo do RainViewer |
| `XDG_CACHE_HOME=/path` | Muda a raiz padrão do cache |

## Estrutura do projeto

```text
src/terrascope/
  __main__.py              python -m terrascope entry point
  assets/                  default configuration and bundled reference data
  core/
    app/                   app lifecycle, input, mouse, and rendering mixins
    ui/                    colors, layout, dialogs, and map drawing
    cli.py config.py       command-line and settings validation
    mapdata.py world.py    geographic data and map state
  layers/
    basemap/               country outlines, labels, and map detail
    daynight/              day/night rendering and astronomy calculations
    flights/               OpenSky API, cache, formatting, and aircraft layer
    weather/               weather, radar, forecast, and earthquake modules
```

O entry point público de console é:

```toml
terrascope = "terrascope.__main__:run"
```

## Fontes de dados

- Natural Earth: contornos de países e de províncias/estados, localidades
- OpenSky Network: posições das aeronaves
- Open-Meteo: clima e previsões das cidades
- RainViewer Weather Maps API: tiles de radar passados (uso pessoal/educacional; atribuição obrigatória)
- Feeds GeoJSON do USGS: sismos
- Cálculos no código no estilo NOAA/Meeus: dia/noite e informações da lua

Os dados de referência embutidos vêm do [Natural Earth 50m Cultural Vectors](https://www.naturalearthdata.com/downloads/50m-cultural-vectors/), que é de domínio público.

Cada fonte tem a sua própria disponibilidade e o seu próprio comportamento de
limite de requisições. Use `--offline` quando quiser rodar apenas com os dados
em cache.

O Terrascope não tem telemetria nem analytics. Quando as camadas ao vivo estão
ativadas, as requisições de rede vão para os provedores de dados configurados.
As requisições de clima incluem as coordenadas das cidades exibidas; os
provedores também recebem o seu endereço IP e o User-Agent do Terrascope.
`--offline` desativa as requisições ao vivo.

## Traduções

A interface usa gettext, domínio `terrascope`. O português do Brasil (`pt_BR`)
está incluído. O idioma é escolhido nesta ordem: `--lang`, `app.language` na
configuração, as variáveis `LANGUAGE` / `LC_ALL` / `LC_MESSAGES` / `LANG`, o
idioma da interface do Windows e, por fim, inglês. O relógio e as unidades
acompanham o idioma: em `pt_BR`, horário de 24 horas, °C, km/h, vírgula decimal
e datas `dd/mm/aaaa`. Substitua-os com `--time-format 24h|12h` e
`--units metric|imperial`, ou com `app.time_format` e `app.units` na
configuração.

Os catálogos ficam em `src/terrascope/locale/<lang>/LC_MESSAGES/terrascope.po`.
Os arquivos `.mo` são compilados no build (`hatch_build.py`, com o Babel) e não
são mantidos no git. Para adicionar um idioma:

```bash
pip install babel
pybabel extract -F babel.cfg -k N_ -o src/terrascope/locale/terrascope.pot .
pybabel init -i src/terrascope/locale/terrascope.pot -d src/terrascope/locale -l de_DE -D terrascope
# translate src/terrascope/locale/de_DE/LC_MESSAGES/terrascope.po, then:
pybabel compile -D terrascope -d src/terrascope/locale
```

Para conferir um layout com um pseudoidioma (texto acentuado e 30% mais longo):

```bash
python tools/pseudo_locale.py /tmp/pseudo
terrascope_LOCALE_DIR=/tmp/pseudo terrascope --lang xx
```

## Verificações de desenvolvimento

Verificação básica de sintaxe:

```bash
python3 -m compileall -q src/terrascope
```

Com as dependências instaladas, um teste rápido de importação é:

```bash
PYTHONPATH=src python3 -c "from terrascope.core.registry import build_layers; print([l.name for l in build_layers()])"
```

## Publicação de versões

As tags de versão geram e publicam no PyPI o wheel e a distribuição de código
fonte, além dos downloads independentes `.tar.gz`, `.deb`, `.rpm` e `.AppImage`
para cada plataforma. Os pacotes `terrascope` e `terrascope-git` do AUR são
publicados a partir de `packaging/aur/`. Veja
[docs/RELEASING.md](docs/RELEASING.md) para as etapas de release e de Git.


[![Star History Chart](https://app.repohistory.com/api/svg?repo=a-shygun/terrascope&type=Date&background=0D1117&color=6278f8)](https://app.repohistory.com/star-history)
## Licença

MIT. Veja `LICENSE`.
