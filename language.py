class dotdict(dict):
    """Dot notation access to dictionary attributes."""
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


english = dotdict({
	"period": "Period",
	"vesset": "Vesset",
	"mark": "Day",
	"Monthly": "Monthly",
	"Thirty": "Thirty",
	"ThirtyOne": "ThirtyOne",
	"LastSkip": "LastSkip",
	"OldSkip": "OldSkip",
	"OrZarua": "Or Zarua",
	"KartiUfalti": "Karti Ufalti"
})

# Terminal display (transliterated)
hebrew = dotdict({
	"period": "Machzor",
	"vesset": "Vesset", 
	"mark": "Yom",
	"Monthly": "Hachodesh",
	"Thirty": "Beinonit",
	"ThirtyOne": "Lamed-Aleph",
	"LastSkip": "Haflagah Achronah",
	"OldSkip": "Haflagah Shelo Ne'ekrah",
	"OrZarua": "Or Zarua",
	"KartiUfalti": "Karti Ufalti"
})

# Calendar events (original Hebrew)
hebrew_calendar = dotdict({
	"period": "מחזור",
	"vesset": "וסת",
	"mark": "יום",
	"Monthly": "החודש",
	"Thirty": "בינונית",
	"ThirtyOne": "ל\"א",
	"LastSkip": "הפלגה אחרונה",
	"OldSkip": "הפלגה שלא נעקרה",
	"OrZarua": "אור זרוע",
	"KartiUfalti": "כרתי ופלתי"
})

language_dict = dotdict({"english": english, "hebrew": hebrew, "hebrew_calendar": hebrew_calendar})