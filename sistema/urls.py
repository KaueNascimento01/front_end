from django.urls import path
from . import views

urlpatterns = [
    path("", views.RegistrarChamado.as_view(), name="cadastrar_chamado"),
    path("ver_analista/<int:user_id>/", views.ver_analista, name="ver_analista"),
    path("views/", views.views, name="views"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/exportar-pdf/", views.exportar_pdf, name="exportar_pdf"),
    path("dashboard/personalizado/<int:user_id>/", views.dashboard_personalizado, name="dashboard_personalizado"),
]