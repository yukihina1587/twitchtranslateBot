"""
TTS読み上げ辞書モジュール
漢字の読み間違いを修正するためのカスタム辞書機能
"""
import json
import os
from typing import Dict, List, Optional
from src.logger import logger


class TTSDictionary:
    """TTS読み上げ辞書クラス"""

    def __init__(self, dictionary_file: str = "tts_dictionary.json"):
        """
        辞書の初期化

        Args:
            dictionary_file: 辞書ファイルのパス
        """
        self.dictionary_file = dictionary_file
        self.dictionary: Dict[str, str] = {}
        self.load()

    def load(self) -> bool:
        """
        辞書ファイルを読み込む

        Returns:
            成功した場合True
        """
        try:
            if os.path.exists(self.dictionary_file):
                with open(self.dictionary_file, 'r', encoding='utf-8') as f:
                    self.dictionary = json.load(f)
                logger.info(f"辞書を読み込みました: {len(self.dictionary)}エントリ")
                return True
            else:
                logger.info("辞書ファイルが存在しないため、新規作成します")
                self.dictionary = {}
                return True
        except Exception as e:
            logger.error(f"辞書の読み込みに失敗: {e}", exc_info=True)
            self.dictionary = {}
            return False

    def save(self) -> bool:
        """
        辞書ファイルに保存

        Returns:
            成功した場合True
        """
        try:
            with open(self.dictionary_file, 'w', encoding='utf-8') as f:
                json.dump(self.dictionary, f, ensure_ascii=False, indent=2)
            logger.info(f"辞書を保存しました: {len(self.dictionary)}エントリ")
            return True
        except Exception as e:
            logger.error(f"辞書の保存に失敗: {e}", exc_info=True)
            return False

    def add_word(self, word: str, reading: str) -> bool:
        """
        単語と読みを追加

        Args:
            word: 登録する単語（例: "漢字"）
            reading: 読み方（例: "かんじ"）

        Returns:
            成功した場合True
        """
        if not word or not reading:
            logger.warning("単語または読みが空です")
            return False

        self.dictionary[word] = reading
        logger.info(f"辞書に追加: {word} → {reading}")
        return self.save()

    def remove_word(self, word: str) -> bool:
        """
        単語を削除

        Args:
            word: 削除する単語

        Returns:
            成功した場合True
        """
        if word in self.dictionary:
            del self.dictionary[word]
            logger.info(f"辞書から削除: {word}")
            return self.save()
        else:
            logger.warning(f"辞書に存在しない単語: {word}")
            return False

    def get_reading(self, word: str) -> Optional[str]:
        """
        単語の読みを取得

        Args:
            word: 単語

        Returns:
            読み（存在しない場合はNone）
        """
        return self.dictionary.get(word)

    def get_all_entries(self) -> List[tuple]:
        """
        全ての辞書エントリを取得

        Returns:
            [(単語, 読み), ...] のリスト
        """
        return list(self.dictionary.items())

    def apply_dictionary(self, text: str) -> str:
        """
        テキストに辞書を適用して読みを置換

        Args:
            text: 元のテキスト

        Returns:
            辞書適用後のテキスト
        """
        result = text
        # 長い単語から順に置換（部分一致を避けるため）
        sorted_words = sorted(self.dictionary.keys(), key=len, reverse=True)

        for word in sorted_words:
            reading = self.dictionary[word]
            result = result.replace(word, reading)

        if result != text:
            logger.debug(f"辞書適用: '{text}' → '{result}'")

        return result

    def clear(self) -> bool:
        """
        辞書を全てクリア

        Returns:
            成功した場合True
        """
        self.dictionary = {}
        logger.info("辞書をクリアしました")
        return self.save()

    def export_to_file(self, filepath: str) -> bool:
        """
        辞書を別のファイルにエクスポート

        Args:
            filepath: エクスポート先のファイルパス

        Returns:
            成功した場合True
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.dictionary, f, ensure_ascii=False, indent=2)
            logger.info(f"辞書をエクスポートしました: {filepath}")
            return True
        except Exception as e:
            logger.error(f"辞書のエクスポートに失敗: {e}", exc_info=True)
            return False

    def import_from_file(self, filepath: str) -> bool:
        """
        別のファイルから辞書をインポート

        Args:
            filepath: インポート元のファイルパス

        Returns:
            成功した場合True
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                imported_dict = json.load(f)

            # 既存の辞書にマージ
            self.dictionary.update(imported_dict)
            logger.info(f"辞書をインポートしました: {len(imported_dict)}エントリ")
            return self.save()
        except Exception as e:
            logger.error(f"辞書のインポートに失敗: {e}", exc_info=True)
            return False


# グローバルインスタンス
_dictionary_instance = None


def get_dictionary() -> TTSDictionary:
    """グローバル辞書インスタンスを取得"""
    global _dictionary_instance
    if _dictionary_instance is None:
        _dictionary_instance = TTSDictionary()
    return _dictionary_instance
