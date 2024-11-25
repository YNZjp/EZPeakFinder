import traceback
import sys
from PyQt5 import QtWidgets, QtCore
import threading
import re
from src.chatdl import TwitchChatDL
from src.analyzecomments import AnalyzeComments
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib import rcParams
from matplotlib import font_manager as fm
from matplotlib.collections import PathCollection
import requests
from bs4 import BeautifulSoup
import webbrowser
import time
import datetime

rcParams["font.family"] = "Meiryo"
font_path = fm.findfont(fm.FontProperties(fname="C:/Windows/Fonts/meiryo.ttc"))
if not font_path:
    print("日本語対応フォントが見つかりません。Matplotlibのフォント設定を確認してください。")


class EZPeakFinder(QtWidgets.QWidget):

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.chat_downloader = None
        self.analyzer = None
        self.last_url = None
        self.cached_comments = None

        self.sensitivity_slider.valueChanged.disconnect()
        self.sensitivity_slider.valueChanged.connect(
            self.update_graph_on_sensitivity_change)

    def init_ui(self):
        self.setWindowTitle("EZPeakFinder")
        self.setGeometry(100, 100, 1200, 900)
        self.setStyleSheet("background-color: #f7f7f7; color: #000000;")

        self.stream_title_label = QtWidgets.QLabel("配信タイトル: 未取得")
        self.stream_title_label.setStyleSheet(
            "font-size: 18px; color: #0077c8;")

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(50, 30, 50, 30)
        main_layout.setSpacing(30)

        # ヘッダエリア
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(20)
        header_layout.setAlignment(QtCore.Qt.AlignLeft)

        url_label = QtWidgets.QLabel("配信URL:")
        url_label.setStyleSheet("font-size: 18px; color: #1a1a1a;")
        self.url_input = QtWidgets.QLineEdit()
        self.url_input.setMinimumWidth(600)
        self.url_input.setStyleSheet(
            "font-size: 16px; padding: 10px; border: 2px solid #b8b8b8; border-radius: 5px; background-color: #ffffff; color: #1a1a1a;"
        )

        self.analyze_button = QtWidgets.QPushButton("解析実行")
        self.analyze_button.setFixedHeight(50)
        self.analyze_button.setFixedWidth(200)
        self.analyze_button.setStyleSheet(
            "font-size: 18px; background-color: #0077c8; color: #ffffff; border-radius: 5px; padding: 10px;"
        )
        self.analyze_button.clicked.connect(self.on_analyze_click)

        header_layout.addWidget(url_label)
        header_layout.addWidget(self.url_input)
        header_layout.addWidget(self.analyze_button)

        # 設定エリア
        settings_layout = QtWidgets.QHBoxLayout()
        settings_layout.setSpacing(20)
        settings_layout.setAlignment(QtCore.Qt.AlignLeft)

        threads_label = QtWidgets.QLabel("スレッド数:")
        threads_label.setStyleSheet("font-size: 18px; color: #1a1a1a;")
        self.threads_input = QtWidgets.QSpinBox()
        self.threads_input.setRange(1, 99)
        self.threads_input.setValue(10)
        self.threads_input.setStyleSheet(
            "font-size: 16px; padding: 5px; border: 2px solid #b8b8b8; border-radius: 5px; background-color: #ffffff; color: #1a1a1a;"
        )

        adjust_label = QtWidgets.QLabel("リンク調整（秒）:")
        adjust_label.setStyleSheet("font-size: 18px; color: #1a1a1a;")
        self.adjust_input = QtWidgets.QSpinBox()
        self.adjust_input.setRange(0, 3600)
        self.adjust_input.setValue(30)
        self.adjust_input.setStyleSheet(
            "font-size: 16px; padding: 5px; border: 2px solid #b8b8b8; border-radius: 5px; background-color: #ffffff; color: #1a1a1a;"
        )

        settings_layout.addWidget(threads_label)
        settings_layout.addWidget(self.threads_input)
        settings_layout.addWidget(adjust_label)
        settings_layout.addWidget(self.adjust_input)

        # 感度レベル設定エリア
        sensitivity_layout = QtWidgets.QHBoxLayout()
        sensitivity_layout.setSpacing(20)
        sensitivity_layout.setAlignment(QtCore.Qt.AlignLeft)

        sensitivity_label = QtWidgets.QLabel("感度レベル (低感度 - 高感度):")
        sensitivity_label.setStyleSheet("font-size: 18px; color: #1a1a1a;")
        self.sensitivity_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.sensitivity_slider.setRange(1, 10)
        self.sensitivity_slider.setValue(5)
        self.sensitivity_slider.setStyleSheet(
            "QSlider::handle:horizontal { background: #0077c8; }")
        self.sensitivity_slider.valueChanged.connect(
            self.update_graph_on_sensitivity_change)

        sensitivity_layout.addWidget(sensitivity_label)
        sensitivity_layout.addWidget(self.sensitivity_slider)

        main_layout.addLayout(header_layout)
        main_layout.addLayout(settings_layout)
        main_layout.addLayout(sensitivity_layout)
        main_layout.addWidget(self.stream_title_label)

        # プログレスインジケータ
        progress_layout = QtWidgets.QVBoxLayout()
        progress_layout.setSpacing(15)
        progress_layout.setAlignment(QtCore.Qt.AlignCenter)

        self.download_progress_label = QtWidgets.QLabel("チャットをダウンロード中...")
        self.download_progress_label.setStyleSheet(
            "font-size: 16px; color: #0077c8;")
        self.download_progress_label.hide()

        self.download_progress_bar = QtWidgets.QProgressBar()
        self.download_progress_bar.setFixedWidth(1000)
        self.download_progress_bar.setStyleSheet(
            "QProgressBar { border: 2px solid #b8b8b8; border-radius: 5px; text-align: center; background: #e6e6e6; } "
            "QProgressBar::chunk { background: #0077c8; }")
        self.download_progress_bar.setRange(0, 100)
        self.download_progress_bar.hide()

        self.analysis_progress_label = QtWidgets.QLabel("解析中...")
        self.analysis_progress_label.setStyleSheet(
            "font-size: 16px; color: #0077c8;")
        self.analysis_progress_label.hide()

        self.analysis_progress_bar = QtWidgets.QProgressBar()
        self.analysis_progress_bar.setFixedWidth(1000)
        self.analysis_progress_bar.setStyleSheet(
            "QProgressBar { border: 2px solid #b8b8b8; border-radius: 5px; text-align: center; background: #e6e6e6; } "
            "QProgressBar::chunk { background: #0077c8; }")
        self.analysis_progress_bar.setRange(0, 0)
        self.analysis_progress_bar.hide()

        progress_layout.addWidget(self.download_progress_label)
        progress_layout.addWidget(self.download_progress_bar)
        progress_layout.addWidget(self.analysis_progress_label)
        progress_layout.addWidget(self.analysis_progress_bar)
        main_layout.addLayout(progress_layout)

        # グラフ描画ゾーン
        self.graph_canvas = FigureCanvas(Figure(figsize=(12, 6)))
        main_layout.addWidget(self.graph_canvas)
        self.graph_canvas.mpl_connect('pick_event', self.on_graph_click)
        self.setLayout(main_layout)

        # グラフ表示オプション
        self.graph_type_dropdown = QtWidgets.QComboBox()
        self.graph_type_dropdown.setStyleSheet(
            "font-size: 16px; padding: 5px; border: 2px solid #b8b8b8; border-radius: 5px; background-color: #ffffff; color: #1a1a1a;"
        )
        self.graph_type_dropdown.addItems(["全て", "ピーク", "通常"])
        self.graph_type_dropdown.currentIndexChanged.connect(
            self.update_graph_display)
        main_layout.addWidget(self.graph_type_dropdown)

    def update_graph_on_sensitivity_change(self):
        try:
            if not hasattr(self, 'analyzer') or not hasattr(
                    self, 'cached_comments'
            ) or self.analyzer is None or self.cached_comments is None:
                print("解析データが存在しません。解析実行後にスライダーを操作してください。")
                return

            sensitivity = self.sensitivity_slider.value()

            self.bins, self.scores, self.peaks = self.analyzer.detect_peaks(
                sensitivity=sensitivity)

            selected_option = self.graph_type_dropdown.currentText()

            if selected_option == "全て":
                self.plot_graph(self.bins,
                                self.scores,
                                self.peaks,
                                show_all=True)
            elif selected_option == "ピーク":
                self.plot_graph(self.bins,
                                self.scores,
                                self.peaks,
                                show_all=False,
                                show_peaks=True,
                                show_normal=False)
            elif selected_option == "通常":
                self.plot_graph(self.bins,
                                self.scores,
                                self.peaks,
                                show_all=False,
                                show_peaks=False,
                                show_normal=True)
        except Exception as e:
            print(f"スライダー操作時に例外が発生しました: {e}")

    def on_analyze_click(self):
        self.update_button_state(False, "実行中...", "#ff9800")

        self.graph_type_dropdown.setCurrentIndex(0)
        self.graph_type_dropdown.setEnabled(False)

        self.reset_graph()

        analysis_thread = threading.Thread(
            target=self.run_analysis_with_logging, daemon=True)
        analysis_thread.start()

    def reset_graph(self):
        self.graph_canvas.figure.clear()
        ax = self.graph_canvas.figure.add_subplot(111)
        ax.set_title("解析結果を待機中...")
        ax.set_xlabel('時間 (hh:mm:ss)')
        ax.set_ylabel('スコア')
        self.graph_canvas.draw()

    def run_analysis_with_logging(self):
        try:
            self.run_analysis()
        except Exception as e:
            QtCore.QMetaObject.invokeMethod(self, "show_error_message",
                                            QtCore.Qt.QueuedConnection,
                                            QtCore.Q_ARG(str, str(e)))
            QtCore.QMetaObject.invokeMethod(self.graph_type_dropdown,
                                            "setEnabled",
                                            QtCore.Qt.QueuedConnection,
                                            QtCore.Q_ARG(bool, True))
            self.update_button_state(True, "解析実行", "#0077c8")

    def run_analysis(self):
        url = self.url_input.text().strip()
        if not url:
            raise ValueError("URLを入力してください。")

        if not self.validate_url(url):
            raise ValueError(
                "URL形式が正しくありません。\n形式: https://www.twitch.tv/videos/XXXXXXXX")

        video_id = self.extract_video_id(url)
        if not video_id:
            raise ValueError("有効な動画IDを取得できません。")

        if self.last_url == url and self.cached_comments is not None:
            print("キャッシュされたチャットデータを使用します。")
            data = {
                "comments": self.cached_comments,
                "video": {
                    "lengthSeconds": self.analyzer.video_length
                }
            }
        else:
            print("新しいURLです。チャットデータをダウンロードします。")
            self.last_url = url
            self.set_progress_state(True, self.download_progress_bar,
                                    self.download_progress_label)
            self.chat_downloader = TwitchChatDL(
                video_id=video_id, num_threads=self.threads_input.value())

            data = self.chat_downloader.download_comments(
                progress_callback=self.update_download_progress)
            self.cached_comments = data["comments"]

            self.set_progress_state(False, self.download_progress_bar,
                                    self.download_progress_label)

        title_thread = threading.Thread(target=self.extract_title_from_url,
                                        args=(url, ))
        title_thread.start()

        self.set_progress_state(True, self.analysis_progress_bar,
                                self.analysis_progress_label)

        self.analyzer = AnalyzeComments(
            comments=data["comments"],
            video_length=data["video"]["lengthSeconds"])

        sensitivity = self.sensitivity_slider.value()

        self.bins, self.scores, self.peaks = self.analyzer.detect_peaks(
            sensitivity=sensitivity)

        self.set_progress_state(False, self.analysis_progress_bar,
                                self.analysis_progress_label)

        self.plot_graph(self.bins, self.scores, self.peaks)

        QtCore.QMetaObject.invokeMethod(self.graph_type_dropdown, "setEnabled",
                                        QtCore.Qt.QueuedConnection,
                                        QtCore.Q_ARG(bool, True))

        self.update_button_state(True, "解析実行", "#0077c8")

    def extract_title_from_url(self, url):

        def title_extraction_thread():
            headers = {
                'User-Agent':
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            retries = 5
            delay = 2

            self.stream_title_label.setText("タイトル取得中...")

            for attempt in range(retries):
                try:
                    response = requests.get(url, headers=headers, timeout=10)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, 'html.parser')

                    title_element = soup.find('meta', {'property': 'og:title'})
                    if title_element and 'content' in title_element.attrs:
                        title = title_element['content']
                        if title.strip() == "Twitch":
                            print(
                                f"試行 {attempt + 1}/{retries}: タイトルが 'Twitch' のみでした。再試行します..."
                            )
                            time.sleep(delay)
                            continue

                        QtCore.QMetaObject.invokeMethod(
                            self.stream_title_label, "setText",
                            QtCore.Qt.QueuedConnection,
                            QtCore.Q_ARG(str, f"配信タイトル: {title}"))
                        return
                    else:
                        print(
                            f"試行 {attempt + 1}/{retries}: タイトルが見つかりませんでした。再試行します..."
                        )
                        time.sleep(delay)
                except requests.RequestException as e:
                    print(f"リクエストエラー (試行 {attempt + 1}/{retries}): {e}")
                    time.sleep(delay)

            QtCore.QMetaObject.invokeMethod(self.stream_title_label, "setText",
                                            QtCore.Qt.QueuedConnection,
                                            QtCore.Q_ARG(str, "タイトル取得失敗"))

        title_thread = threading.Thread(target=title_extraction_thread,
                                        daemon=True)
        title_thread.start()

    @QtCore.pyqtSlot(str)
    def show_error_message(self, error_message):
        QtWidgets.QMessageBox.critical(self, "エラー", error_message)
        self.update_button_state(True, "解析実行", "#0077c8")

    def validate_url(self, url):
        pattern = r"^https://(www\.)?twitch\.tv/videos/\d+$"
        return bool(re.match(pattern, url.strip()))

    def set_progress_state(self, state: bool, progress_bar, progress_label):
        progress_bar.setVisible(state)
        progress_label.setVisible(state)

    def update_download_progress(self, progress):
        self.download_progress_bar.setValue(int(progress))

    def plot_graph(self,
                   bins,
                   scores,
                   peaks,
                   show_all=True,
                   show_peaks=True,
                   show_normal=True):
        bins = bins[:len(scores)]
        self.graph_canvas.figure.clear()
        ax = self.graph_canvas.figure.add_subplot(111)

        normal_count = len(scores) - len(peaks)
        peak_count = len(peaks)

        if show_all or show_normal:
            ax.plot(bins,
                    scores,
                    color='blue',
                    label=f'通常 ({normal_count}点)',
                    linewidth=1.5,
                    alpha=0.7)
            self.line_normal = ax.scatter(bins,
                                          scores,
                                          color='blue',
                                          label=None,
                                          s=30,
                                          picker=5)

        if show_all or show_peaks:
            peak_bins = bins[peaks]
            peak_scores = scores[peaks]
            ax.plot(peak_bins,
                    peak_scores,
                    color='red',
                    label=f'ピーク ({peak_count}点)',
                    linewidth=1.5,
                    alpha=0.7)
            self.line_peaks = ax.scatter(peak_bins,
                                         peak_scores,
                                         color='red',
                                         label=None,
                                         s=50,
                                         picker=10)

        ax.set_xlabel('時間 (hh:mm:ss)')
        ax.set_ylabel('スコア')

        ax.set_xticks(bins[::len(bins) // 10])
        ax.set_xticklabels([
            str(datetime.timedelta(seconds=int(tick)))
            for tick in bins[::len(bins) // 10]
        ])

        ax.legend()
        ax.grid(True)
        self.graph_canvas.draw()

    def on_graph_click(self, event):
        if event.name != 'pick_event':
            return

        scatter = event.artist
        if not isinstance(scatter, PathCollection):
            return

        indices = event.ind
        if len(indices) == 0:
            return

        index = indices[0]
        clicked_time = scatter.get_offsets()[index][0]

        current_time = time.time()
        cooldown_period = 2

        if hasattr(self, "last_opened_time") and hasattr(
                self, "last_click_timestamp"):
            if self.last_opened_time == clicked_time and (
                    current_time - self.last_click_timestamp
                    < cooldown_period):
                return

        self.last_opened_time = clicked_time
        self.last_click_timestamp = current_time

        adjust_seconds = self.adjust_input.value()
        adjusted_time = max(0, clicked_time - adjust_seconds)
        hours, remainder = divmod(adjusted_time, 3600)
        minutes, seconds = divmod(remainder, 60)
        time_param = f"?t={int(hours)}h{int(minutes)}m{int(seconds)}s"

        video_id = self.extract_video_id(self.url_input.text())
        if video_id:
            full_url = f"https://www.twitch.tv/videos/{video_id}{time_param}"
            webbrowser.open(full_url)

    def update_button_state(self, enabled, text=None, color=None):
        self.analyze_button.setEnabled(enabled)
        if text:
            self.analyze_button.setText(text)
        if color:
            self.analyze_button.setStyleSheet(
                f"font-size: 18px; border-radius: 5px; padding: 10px; background-color: {color}; color: #ffffff;"
            )

    @staticmethod
    def extract_video_id(url):
        match = re.search(r"videos/(\d+)", url)
        return match.group(1) if match else None

    def update_graph_display(self):
        selected_option = self.graph_type_dropdown.currentText()

        if hasattr(self, 'bins') and hasattr(self, 'scores') and hasattr(
                self, 'peaks'):
            if selected_option == "全て":
                self.plot_graph(self.bins,
                                self.scores,
                                self.peaks,
                                show_all=True)
            elif selected_option == "ピーク":
                self.plot_graph(self.bins,
                                self.scores,
                                self.peaks,
                                show_all=False,
                                show_peaks=True,
                                show_normal=False)
            elif selected_option == "通常":
                self.plot_graph(self.bins,
                                self.scores,
                                self.peaks,
                                show_all=False,
                                show_peaks=False,
                                show_normal=True)


def global_exception_hook(exc_type, exc_value, exc_traceback):
    print("未処理の例外が発生しました:")
    traceback.print_exception(exc_type,
                              exc_value,
                              exc_traceback,
                              file=sys.stdout)
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def main():
    sys.excepthook = global_exception_hook
    app = QtWidgets.QApplication(sys.argv)
    window = EZPeakFinder()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
