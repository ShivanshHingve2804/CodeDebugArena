# Challenge 08: Unicode Normalization Bug
**Category:** String/Encoding | **Difficulty:** ⭐⭐⭐ | **Root Cause:** NFC ('é') and NFD ('e' + combining accent) look identical but fail equality
