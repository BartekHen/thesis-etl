from app.auth import get_access_token
from app.http import allegro_get

token = get_access_token(1)
data = allegro_get("/order/checkout-forms", token, {"limit": 1})
print(data.get("totalCount"), "zamowien lacznie")