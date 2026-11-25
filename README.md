# teslim

Bir repoyu public yapmadan ya da sürüm çıkarmadan önceki **son kontrol** ve ona bağlı **yayın kapısı**.
`teslim` repoyu tüm geçmişiyle tarar; her şey temizse süreli bir fiş yazar. `teslim-kapi` bir Claude Code
`PreToolUse` hook'udur: geçerli fiş yoksa ajanın repoyu public yapmasını, sürüm çıkarmasını ve tag göndermesini
reddeder.

Yalnız standart kütüphane, Python 3.11+, Windows ve POSIX. `git` ve GitHub kontrolleri için `gh` komutlarını
çağırır. Model çağrısı yok.

**English summary.** `teslim` is a dependency-free pre-publish check for GitHub repositories. Before a repo goes
public or a release/tag is cut, it verifies that the git identity uses a GitHub noreply address, scans the
*entire* history (all branches, tags, and commits left dangling by force-pushes, fetched via the GitHub activity
and events APIs) for e-mail addresses, names from a private list, Turkish national ID numbers, secret patterns,
home-directory paths and user-configured internal markers, provider-name lists, internal-document and secret-file
paths, checks that README and LICENSE exist, and that CI is green on the latest commit. If everything passes it
writes a time-limited receipt bound to a hash of all remote refs. `teslim-kapi` is a Claude Code `PreToolUse` hook
that denies `gh repo edit --visibility public`, `gh release create`, `gh api ... private=false|visibility=public`
and tag-pushing `git push` unless a valid receipt exists, and always denies `gh repo create --public`. Findings
are reported by type and location only, never by value. Every personal pattern lives in the user's own config
file outside the repo. Docs and identifiers are Turkish.

## Kurulum

```
pip install -e .            # teslim, teslim-gecmis ve teslim-kapi komutları
pip install -e ".[dev]"     # + pytest, ruff
```

## Hızlı başlangıç

```
mkdir -p ~/.config/teslim
cp ornek/ayar.ornek.toml ~/.config/teslim/ayar.toml          # kendi iç izlerini ve kalıplarını yaz
cp ornek/kisisel-adlar.ornek.txt ~/.config/teslim/kisisel-adlar.txt   # kendi adlarını yaz

teslim --dizin ~/kod/yeni-repo     # göndermeden önce yerel ön kontrol, fiş yazmaz
# repoyu private olarak gönder, CI'ın bitmesini bekle
teslim sahip/yeni-repo             # tüm kontroller; geçerse fiş yazar
gh repo edit sahip/yeni-repo --visibility public --accept-visibility-change-consequences
```

Windows'ta ayar dizini `%APPDATA%\teslim\` olur.

## Komutlar

| Komut | Ne yapar | Çıkış |
|---|---|---|
| `teslim SAHIP/REPO` | Dört kontrol (aşağıda); hepsi geçerse fiş yazar. Başlarken eski fişi siler: yarım kalan kontrol eski fişi geçerli bırakmaz. | 0 geçti, 1 kaldı, 2 kontrol yapılamadı |
| `teslim --dizin YOL` | Aynı kontroller yerel kopyada (CI hariç); fiş yazmaz. | aynı |
| `teslim-gecmis [--repo YOL \| --github SAHIP/REPO] [--aralik A..B]` | Yalnız geçmiş taraması. `--aralik` CI'da yeni commit'ler için; `--json` makine çıktısı; `--adlar-zorunlu` ad listesi yoksa 2 ile çıkar. | 0 temiz, 1 bulgu, 2 hata |
| `teslim-kapi` | Hook kipi: stdin'den hook JSON'u okur, gerekirse ret JSON'u basar. | her zaman 0 |
| `teslim-kapi --komut "..." [--dizin YOL]` | Bir komutun kapıdan geçip geçmeyeceğini elle dener. | 0 geçer, 1 ret |

Çıkış 2 hiçbir zaman "geçti" sayılmaz: ad listesi yoksa, ayar dosyası bozuksa, `gh`/`git` çalışmadıysa ya da
force-push'la dalsız kalmış bir commit çekilemediyse kontrol yapılmamış demektir.

## Kontroller

| Kontrol | Geçme şartı |
|---|---|
| git kimliği | commit e-postası `@users.noreply.github.com` (yerel kipte repodaki etkin ayar, aksi halde global) |
| geçmiş taraması | tüm dallar, tag'ler ve dalsız commit'lerde bulgu yok, taranamayan büyük dosya yok |
| ürün dosyaları | kökte README ve LICENSE (ya da LICENCE/COPYING) |
| CI | son commit'te en az bir iş başarılı; başarısız ya da bitmemiş iş yok |

Geçmiş taramasının türleri:

| Tür | Nerede | Kaynak |
|---|---|---|
| yazar / committer / tagger e-postası | commit ve tag üst verisi | yerleşik; noreply, `example.*`, `.test` gibi ayrılmış alanlar izinli |
| e-posta | mesajlar, dosyalar (ikili dosyalar dahil) | yerleşik |
| ad | mesajlar, dosyalar | senin ad listen (`kisisel-adlar.txt`) |
| TC kimlik no | mesajlar, metin dosyaları | yerleşik, sağlama haneleriyle doğrulanır |
| sır kalıbı | mesajlar, metin dosyaları | yerleşik (API anahtarı ve özel anahtar kalıpları) |
| kişisel altyapı izi | mesajlar, metin dosyaları | yerleşik ev dizini yolları + ayardaki `ic_iz` |
| sağlayıcı listesi | metin dosyaları | ayardaki `saglayicilar`, tek dosyada `saglayici_esik` kadar |
| iç belge | geçmişte bulunmuş yollar | ayardaki `ic_belge` glob'ları |
| sır dosyası | geçmişte bulunmuş yollar | yerleşik (`.env`, `*.pem`, `*.key`, `id_rsa`, `auth.json` ...) |

Silinmiş dosyalar, yeniden adlandırılmış yollar ve force-push'la dallardan düşmüş commit'ler de taranır.
Çıktı bulgunun **değerini asla yazmaz**, yalnız türünü ve yerini (`commit abc1234567`, `dosya docs/x.md`).

## Fiş

Fiş, `<ayar dizini>/teslim/fis/<sahip>__<repo>.json` dosyasıdır: repo adı, kontrol anındaki tüm uzak ref'lerin
(`git ls-remote`) özeti, kontrol edilen commit ve zaman. Ref özeti taramadan **önce** alınır; tarama sırasında
gelen bir push fişi kendiliğinden geçersiz bırakır. Fiş şu durumlarda geçersizdir:

- süresi doldu (`gecerlilik_saat`, varsayılan 24) ya da zamanı gelecekte,
- repoda herhangi bir dal, tag ya da PR ucu değişti,
- dosya başka bir repoya ait, bozuk ya da yok.

## Yayın kapısı (Claude Code hook'u)

`~/.claude/settings.json` (bütün projeler) ya da projenin `.claude/settings.json` dosyasına:

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash|PowerShell", "hooks": [{ "type": "command", "command": "teslim-kapi", "timeout": 60 }] }
    ]
  }
}
```

| Komut | Karar |
|---|---|
| `gh repo edit [SAHIP/REPO] --visibility public` | fişe bağlı |
| `gh release create ... [-R SAHIP/REPO]` | fişe bağlı |
| `gh api ... repos/SAHIP/REPO ... private=false` ya da `visibility=public` | fişe bağlı |
| `git push --tags`, `--follow-tags`, `--mirror`, `refs/tags/...`, `git push origin v1.2.0` | fişe bağlı |
| `gh repo create --public` | her zaman ret: önce private kur, kontrol geçince aç |
| diğer her şey | dokunulmaz (çıktı yok) |

Hedef repo komuttan (`SAHIP/REPO`, `-R`, `--repo`, `repos/...`, uzak URL) ya da çalışma dizinindeki `origin`
uzağından bulunur; `cd` ve `git -C` izlenir. Hedef bulunamazsa ret. Commit mesajı (`-m`), PR/sürüm gövdesi
(`--body`, `--notes`, `--title`) ve heredoc içindeki metin komut sayılmaz. Yayın komutu gibi görünen ama
çözülemeyen ya da çok uzun metin reddedilir.

**Kapsamadıkları:** GitHub web arayüzü, kendi terminalinde elle yazdığın komutlar, hook'u kaydetmemiş başka
araçlar. Kapı ajanın kazara yayın yapmasını önler; kasıtlı bir kişiyi durdurmak için tasarlanmadı.

## Ayar

Kişiye özel hiçbir şey repoda değildir; hepsi kullanıcı ayar dizininden ya da ortam değişkeninden okunur:

| Ne | Öncelik sırası |
|---|---|
| ayar dosyası | `TESLIM_AYAR` > `~/.config/teslim/ayar.toml` (`$XDG_CONFIG_HOME`; Windows `%APPDATA%\teslim\`) |
| ad listesi | `TESLIM_ADLAR` > ayardaki `adlar_dosyasi` > `<ayar dizini>/kisisel-adlar.txt` |
| fiş dizini | `TESLIM_FIS_DIZIN` > ayardaki `fis_dizini` > `<ayar dizini>/fis` |

Ayar anahtarları ve örnek değerler: [`ornek/ayar.ornek.toml`](ornek/ayar.ornek.toml). Ayar dosyası yoksa
yerleşik kalıplar kullanılır ve rapor hangi kullanıcı kalıplarının boş olduğunu söyler; ayar dosyası bozuksa
kontrol yapılmaz (çıkış 2). Ad listesi `teslim` için zorunludur.

## Elle kontrol

Tarama dosyanın anlamını okuyamaz. Fiş alındıktan sonra, açmadan önce şunlara dosyaları okuyarak bakılır:

- README ve belgeler yalnız ürünü anlatıyor; plan, yol haritası, iç karar, kişisel hedef yok.
- Örnek adresler ve yollar kişiye ya da makineye bağlanmıyor.
- Örnek veri, ekran görüntüsü, GIF ve video gerçek kişisel içerik göstermiyor (tarama görselin içini okuyamaz).
- Sağlayıcı/model adları tek dosyada eşiğin altında kalıp yine de bir liste gibi duruyorsa çıkarılır.
- Kurulum ve örnek komutlar boş bir makinede README'de anlatıldığı gibi çalışıyor.
- GitHub hesabında e-posta gizliliği (`Keep my email addresses private`) açık.
- Issue, PR açıklaması ve yorumlar repo açılınca görünür; geçmişi temiz yeni repoda bunlar taşınmaz.

Geçmişte bulgu varsa temizlik force-push ile yapılmaz: eski commit'ler GitHub'da erişilebilir kalır. Temiz
geçmişle yeni repo açılır, eskisi private kalır.

## Claude Code skill'i

[`ornek/claude-skill/teslim/SKILL.md`](ornek/claude-skill/teslim/SKILL.md) adım listesini bir skill olarak verir:
`~/.claude/skills/teslim/` altına kopyalanınca ajan "repoyu aç", "sürüm çıkar" gibi isteklerde bu sırayı izler.

## Geliştirme

```
pip install -e ".[dev]"
python -m pytest -q -p no:cacheprovider
python -m ruff check src tests
```

Testler geliştiricinin kendi ayar, ad listesi ve fiş dizinine dokunmaz; ağ çağrısı yapmaz (uzak repolar yerel
bare repolarla taklit edilir).

## Lisans

MIT. Ayrıntı: [LICENSE](LICENSE).
