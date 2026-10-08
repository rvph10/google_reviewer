from app.text import original_text, too_similar


def test_keeps_plain_comment():
    assert original_text("  Super service  ") == "Super service"


def test_strips_translation_after_original():
    comment = "(Translated by Google) Good bread.\n\n(Original)\nLekker brood."
    assert original_text(comment) == "Lekker brood."


def test_strips_translation_appended():
    comment = "Lekker brood.\n\n(Translated by Google)\nGood bread."
    assert original_text(comment) == "Lekker brood."


def test_similarity():
    assert too_similar("Merci beaucoup Sophie, à bientôt !", ["Merci beaucoup Sophie, a bientot"])
    assert not too_similar("Thanks Tom, we will check the invoice.", ["Merci Sophie pour les croissants !"])
