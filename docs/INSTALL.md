# インストール手順

> **対象読者**: VOICEVOX を使ったことはあるけれど、Python やターミナル（黒い画面）には触れたくないかた向けの導入ガイドです。

このページでは **Windows での手順を中心に** 案内します。macOS のかたは末尾の「macOS の場合」をご覧ください。

すべて画面操作（マウスのみ）で完結します。コマンド入力は基本的に必要ありません。

---

## 1. VOICEVOX 本体を入れる

まずは VOICEVOX 本体を最新版にします。

1. ブラウザで公式サイトを開きます: <https://voicevox.hiroshiba.jp/>
2. ページ中ほどの「ダウンロード」ボタンを押し、ご自身の OS（Windows / macOS）を選びます。
3. ダウンロードされたインストーラーをダブルクリックして、画面の案内どおりにインストールします。
4. すでに古い VOICEVOX をお使いの場合も、そのまま上書きインストールして大丈夫です。

![VOICEVOX 公式サイトのダウンロードボタン](images/install_step1.png)

> **すでに最新版を入れている方は、このステップは飛ばして構いません。**

---

## 2. DiffSingerConnector.vvpp をダウンロードする

本コネクターの配布ファイルを入手します。

1. GitHub のリリースページを開きます（このリポジトリの「Releases」タブ）。
2. 一番新しいリリースの「Assets（添付ファイル）」のなかから、自分の環境に合う `.vvpp` をダウンロードします。
   Windows: **`DiffSingerConnector-<version>-windows.vvpp`**
   Apple Silicon Mac: **`DiffSingerConnector-<version>-macos-arm64.vvpp`**
   Intel Mac: **`DiffSingerConnector-<version>-macos-x64.vvpp`**
3. ダウンロード先（通常は「ダウンロード」フォルダ）にファイルが保存されたことを確認します。

![GitHub Releases で .vvpp をダウンロードする様子](images/install_step2.png)

> **VVPP（ぶいぶいピーピー）とは？** VOICEVOX 公式が定めた「エンジン追加用パッケージ」のファイル形式です。VOICEVOX に関連付けられているので、ダブルクリックするだけで導入できます。

---

## 3. ダブルクリックで VOICEVOX に追加する

ダウンロードした `.vvpp` をダブルクリックしてください。

1. 自動的に VOICEVOX エディタが起動します。
2. 「エンジンを追加しますか？」というダイアログが表示されます。
3. **「はい」** をクリックします。
4. 追加処理が終わるまで数十秒お待ちください（モデルや内部ファイルが展開されます）。

![「エンジンを追加しますか？」ダイアログ](images/install_step3.png)

> **うまく VOICEVOX が起動しない場合**: ファイルを右クリック →「プログラムから開く」→「VOICEVOX」を選んでみてください。

---

## 4. エンジン一覧で確認する

導入できたかどうかを確認します。

1. VOICEVOX エディタの画面右上の歯車マーク（または「設定」メニュー）から **「設定」→「エンジン」** を開きます。
2. 一覧に **「DiffSinger Connector」** が並んでいれば成功です。
3. 状態が「実行中」または緑色の表示になっていることを確認します。

![エンジン一覧に DiffSinger Connector が表示されている様子](images/install_step4.png)

> 表示されない場合は [TROUBLESHOOTING.md](TROUBLESHOOTING.md) の「歌手リストに DiffSinger が出てこない」を参照してください。

---

## 5. 歌う画面で DiffSinger 歌手を選ぶ

最後に、実際に DiffSinger を使ってみます。

1. VOICEVOX エディタの上部メニューから **「ソング」**（歌う）画面に切り替えます。
2. 左側の歌手選択エリアをクリックすると、歌手の一覧が出てきます。
3. **「DiffSinger」配下** にあなたが配置したモデル名が表示されているはずです（モデルの配置がまだの場合は次のステップへ）。
4. 歌手を選び、ノートを打ち込んで歌詞をひらがなで入力し、再生ボタンを押すと歌います。

![ソング画面で DiffSinger 歌手を選んでいるところ](images/install_step5.png)

> 歌手が一人もいない、または「モデルが見つかりません」と表示される場合は、続けて [MODEL_SETUP.md](MODEL_SETUP.md) を参照してモデルを配置してください。

---

## macOS の場合

基本的な流れは Windows と同じです。

1. VOICEVOX 公式サイトから macOS 版インストーラー（`.dmg`）をダウンロードして開き、アプリを「アプリケーション」フォルダにドラッグします。
2. GitHub Releases から、お使いの Mac に合う `.vvpp` をダウンロードします。
   Apple Silicon (M1/M2/M3 など): **`DiffSingerConnector-<version>-macos-arm64.vvpp`**
   Intel Mac: **`DiffSingerConnector-<version>-macos-x64.vvpp`**
3. Finder でダウンロードした `.vvpp` をダブルクリック → VOICEVOX が起動して「エンジンを追加しますか？」と聞かれるので「はい」を選びます。
4. 「開発元が未確認です」と出た場合は、Finder で `.vvpp` を右クリック →「開く」を選び、もう一度「開く」を押すと進めます。
5. あとは Windows 手順の 4 番以降と同じです。

---

## うまくいかないとき

トラブル別の対処法を [TROUBLESHOOTING.md](TROUBLESHOOTING.md) にまとめています。先にそちらをご覧ください。

---

## 次に読むべき記事

- 歌手モデルの入手と配置 → [MODEL_SETUP.md](MODEL_SETUP.md)
- 困ったとき → [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
