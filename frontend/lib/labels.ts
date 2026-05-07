export type Period = "ht" | "h2" | "ft";

export interface PeriodLabels {
  prefix: string;
  sonuc: string;
  hnd: string;
  combo15: string;
  combo25: string;
  comboKg: string;
  fark: string;
  taraf: string;
  toplamGol: string;
}

export function periodLabels(period: Period): PeriodLabels {
  if (period === "ht") {
    return {
      prefix: "İY",
      sonuc: "1. Yarı Sonucu",
      hnd: "Handikaplı 1. Yarı",
      combo15: "1. Yarı Sonucu ve 1.5 Alt/Üst",
      combo25: "1. Yarı Sonucu ve 2.5 Alt/Üst",
      comboKg: "1. Yarı Sonucu ve KG",
      fark: "Hangi Takım Kaç Farkla Kazanır? (1. Yarı)",
      taraf: "Taraf Alt/Üst (1. Yarı)",
      toplamGol: "Toplam Gol (1. Yarı)",
    };
  }
  if (period === "h2") {
    return {
      prefix: "2Y",
      sonuc: "2. Yarı Sonucu",
      hnd: "Handikaplı 2. Yarı",
      combo15: "2. Yarı Sonucu ve 1.5 Alt/Üst",
      combo25: "2. Yarı Sonucu ve 2.5 Alt/Üst",
      comboKg: "2. Yarı Sonucu ve KG",
      fark: "Hangi Takım Kaç Farkla Kazanır? (2. Yarı)",
      taraf: "Taraf Alt/Üst (2. Yarı)",
      toplamGol: "Toplam Gol (2. Yarı)",
    };
  }
  return {
    prefix: "MS",
    sonuc: "Maç Sonucu",
    hnd: "Handikaplı MS",
    combo15: "MS Sonucu ve 1.5 Alt/Üst",
    combo25: "MS Sonucu ve 2.5 Alt/Üst",
    comboKg: "MS Sonucu ve Karşılıklı Gol",
    fark: "Hangi Takım Kaç Farkla Kazanır?",
    taraf: "Taraf Alt/Üst",
    toplamGol: "Toplam Gol",
  };
}
