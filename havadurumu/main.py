import sys
import json
import requests
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QMessageBox, QComboBox, QCheckBox
)
from PyQt5.QtGui import QPixmap, QPalette, QColor
from PyQt5.QtCore import Qt, QTimer
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from dotenv import load_dotenv
import os

load_dotenv()  # .env dosyasını yükler

api_key = os.getenv("API_KEY")
if not api_key:
    raise Exception("API_KEY .env dosyasından yüklenemedi! Lütfen .env dosyasına API_KEY ekleyin.")

def temizle_sehir_adi(sehir):
    sehir = sehir.strip().lower()
    karakter_haritasi = str.maketrans("çşğüöı", "csguoi")
    return sehir.translate(karakter_haritasi)

def ip_ile_sehir_bul():
    try:
        response = requests.get("https://ipinfo.io/json")
        data = response.json()
        return data.get("city", "Istanbul")
    except:
        return "Istanbul"

def hava_durumu_getir(sehir):
    sehir = temizle_sehir_adi(sehir)
    URL = f"https://api.openweathermap.org/data/2.5/weather?q={sehir}&appid={api_key}&lang=tr&units=metric"
    response = requests.get(URL)
    data = response.json()

    if response.status_code == 200:
        return {
            "sehir": data["name"],
            "sicaklik": data["main"]["temp"],
            "durum": data["weather"][0]["description"],
            "ikon": data["weather"][0]["icon"]
        }
    else:
        raise ValueError(data.get("message", "Şehir bulunamadı"))

def haftalik_tahmin_getir(sehir):
    sehir = temizle_sehir_adi(sehir)
    URL = f"https://api.openweathermap.org/data/2.5/forecast?q={sehir}&appid={api_key}&lang=tr&units=metric"
    response = requests.get(URL)
    data = response.json()

    if response.status_code == 200:
        tahmin_listesi = []
        grafik_data = []
        for i in range(0, len(data["list"]), 8):
            item = data["list"][i]
            tarih = datetime.fromtimestamp(item["dt"]).strftime("%d.%m")
            durum = item["weather"][0]["description"]
            sicaklik = item["main"]["temp"]
            tahmin_listesi.append(f"{tarih}: {durum.capitalize()} - {sicaklik}°C")
            grafik_data.append((tarih, sicaklik))
        return tahmin_listesi, grafik_data
    else:
        raise ValueError("Haftalık tahmin alınamadı")

def kaydet_log(veri):
    with open("hava_durumu_log.txt", "a", encoding="utf-8") as f:
        f.write(json.dumps(veri, ensure_ascii=False) + "\n")

def yukle_ayarlar():
    try:
        with open("settings.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"tema": "light"}

def kaydet_ayarlar(ayarlar):
    with open("settings.json", "w", encoding="utf-8") as f:
        json.dump(ayarlar, f, indent=4)

class HavaDurumuApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hava Durumu Uygulaması (Gelişmiş + Grafik)")
        self.setGeometry(200, 100, 500, 600)

        self.ayarlar = yukle_ayarlar()

        self.layout = QVBoxLayout()

        self.sehir_input = QLineEdit()
        self.sehir_input.setPlaceholderText("Şehir ismi girin veya boş bırakın (otomatik)")

        self.goster_button = QPushButton("Hava Durumunu Göster")
        self.goster_button.clicked.connect(self.hava_durumunu_goster)

        self.ikon_label = QLabel("")
        self.ikon_label.setAlignment(Qt.AlignCenter)

        self.sonuc_label = QLabel("")
        self.sonuc_label.setAlignment(Qt.AlignCenter)

        self.haftalik_label = QLabel("")
        self.haftalik_label.setWordWrap(True)

        self.tema_secici = QComboBox()
        self.tema_secici.addItems(["light", "dark"])
        self.tema_secici.setCurrentText(self.ayarlar.get("tema", "light"))
        self.tema_secici.currentTextChanged.connect(self.temayi_degistir)

        self.otomatik_guncelleme = QCheckBox("Otomatik güncelle (30sn)")
        self.otomatik_guncelleme.stateChanged.connect(self.zamanlayici_kontrol)

        self.canvas = FigureCanvas(plt.Figure(figsize=(5, 3)))
        self.ax = self.canvas.figure.subplots()

        self.layout.addWidget(self.sehir_input)
        self.layout.addWidget(self.goster_button)
        self.layout.addWidget(self.ikon_label)
        self.layout.addWidget(self.sonuc_label)
        self.layout.addWidget(self.haftalik_label)
        self.layout.addWidget(self.canvas)
        self.layout.addWidget(self.tema_secici)
        self.layout.addWidget(self.otomatik_guncelleme)

        self.setLayout(self.layout)
        self.temayi_degistir(self.tema_secici.currentText())

        self.timer = QTimer()
        self.timer.timeout.connect(self.hava_durumunu_goster)

    def zamanlayici_kontrol(self, durum):
        if durum == Qt.Checked:
            self.timer.start(30000)
        else:
            self.timer.stop()

    def temayi_degistir(self, tema):
        palette = QPalette()
        if tema == "dark":
            palette.setColor(QPalette.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.WindowText, Qt.white)
        else:
            palette.setColor(QPalette.Window, Qt.white)
            palette.setColor(QPalette.WindowText, Qt.black)
        self.setPalette(palette)
        self.ayarlar["tema"] = tema
        kaydet_ayarlar(self.ayarlar)

    def hava_durumunu_goster(self):
        sehir = self.sehir_input.text().strip()
        if not sehir:
            sehir = ip_ile_sehir_bul()
            self.sehir_input.setText(sehir)

        try:
            veri = hava_durumu_getir(sehir)
            self.sonuc_label.setText(f"{veri['sehir']}\n{veri['durum'].capitalize()}\n{veri['sicaklik']}°C")
            self.goster_ikon(veri['ikon'])

            haftalik, grafik_veri = haftalik_tahmin_getir(sehir)
            self.haftalik_label.setText("\n".join(haftalik))
            kaydet_log(veri)

            self.grafik_ciz(grafik_veri)

        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

    def goster_ikon(self, ikon_kodu):
        try:
            ikon_url = f"http://openweathermap.org/img/wn/{ikon_kodu}@2x.png"
            response = requests.get(ikon_url)
            pixmap = QPixmap()
            pixmap.loadFromData(response.content)
            self.ikon_label.setPixmap(pixmap)
        except:
            self.ikon_label.clear()

    def grafik_ciz(self, veri):
        self.ax.clear()
        gunler = [t[0] for t in veri]
        sicakliklar = [t[1] for t in veri]
        self.ax.plot(gunler, sicakliklar, marker='o', linestyle='-', color='royalblue')
        self.ax.set_title("5 Günlük Tahmini Sıcaklık")
        self.ax.set_ylabel("°C")
        self.ax.grid(True)
        self.canvas.draw()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    pencere = HavaDurumuApp()
    pencere.show()
    sys.exit(app.exec_())
