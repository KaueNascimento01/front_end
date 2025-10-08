from django.views import View
from django.shortcuts import render, redirect
from .models import Chamados
from django.contrib.auth.models import User
from datetime import datetime, date, timedelta
import plotly.graph_objects as go
import plotly.express as px
from django.db.models import Count, Sum, Q, Avg
from django.db.models.functions import TruncDate, TruncMonth
from django.core.cache import cache
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import pandas as pd
import json




def ver_analista(request, user_id):
    hora = datetime.strptime("01:00","%H:%M").time()



    analista = User.objects.get(id=user_id)
    chamados_feitos = Chamados.objects.filter(nome_analista=analista)
    analista = str(analista).replace("_", " ")

    return render(request, "chamado_especifico.html" , {"chamados": chamados_feitos, "analista": analista, "hora": hora} )



def views(request):
    
    hora = datetime.strptime("01:00", "%H:%M").time()
    data = date.today()

    quantidade = Chamados.objects.filter(data=data).count()
    chamados  = Chamados.objects.all()
    return render(request, "visualização.html",  {"chamados":chamados, "quantidade": quantidade,"data":data, "hora":hora})



class RegistrarChamado(View):

    def get(self, request):
        return render(request, "index.html")
    

    def post(self, request):
        self.nome_analista = request.POST.get("nome_analista")
        self.ID_chamado = request.POST.get("ID_chamado")
        self.tipo_atividade = request.POST.get("tipo_atividade")
        self.nome_tecnico = request.POST.get("tecnico")
        self.data = request.POST.get("data")
        self.inicio =  request.POST.get("inicio")
        self.conclusao = request.POST.get("conclusao")
        self.situacao = request.POST.get("produtiva")
        self.senha = request.POST.get("senha")
        self.observacao = request.POST.get("observacao")



    
        RegistrarChamado._validar_situacao(self)
        RegistrarChamado._cauculo_de_tempo_de_atendimento(self)
        RegistrarChamado._salvador_chamado(self)
            
        return render(request, "index.html")

    


    def _validar_situacao(self):
        if self.situacao == "on":

            self.situacao = True
        
        else:
            self.situacao = False
   
        
    def _cauculo_de_tempo_de_atendimento(self):
        formato = "%H:%M"

        inicio = datetime.strptime(self.inicio, formato)
        conclusao = datetime.strptime(self.conclusao, formato)
        self.total_horas = str(conclusao - inicio)
    

    def _salvador_chamado(self):
            print(self.tipo_atividade)

            Chamados.objects.create(
                nome_analista = User.objects.get(username=self.nome_analista),
                ID_chamado = self.ID_chamado,
                tipo_atividade = self.tipo_atividade,
                nome_tecnico = self.nome_tecnico,
                data = self.data,
                inicio =  self.inicio,
                conclusao = self.conclusao,
                total_horas = self.total_horas,
                produtiva = self.situacao,
                senha = self.senha,
                observacao = self.observacao,
            )

            
def dashboard(request):
    """
    Dashboard avançado com filtros, cache e análises detalhadas
    """
    # === FILTROS DE PERÍODO ===
    periodo = request.GET.get('periodo', 'todos')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    
    # Aplicar filtros de data
    chamados = Chamados.objects.all()
    
    if periodo == 'semana':
        data_inicio = date.today() - timedelta(days=7)
        data_fim = date.today()
    elif periodo == 'mes':
        data_inicio = date.today() - timedelta(days=30)
        data_fim = date.today()
    elif periodo == 'ano':
        data_inicio = date.today() - timedelta(days=365)
        data_fim = date.today()
    elif data_inicio and data_fim:
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
    
    if periodo != 'todos':
        chamados = chamados.filter(data__range=[data_inicio, data_fim])
    
    # Cache key baseado nos filtros
    cache_key = f"dashboard_data_{periodo}_{data_inicio}_{data_fim}"
    
    # Tentar usar cache, mas continuar se falhar
    try:
        cached_data = cache.get(cache_key)
        if cached_data:
            context = cached_data
            context['periodo_atual'] = periodo
            context['data_inicio'] = data_inicio
            context['data_fim'] = data_fim
            return render(request, 'dashboard.html', context)
    except Exception as e:
        # Se o cache falhar, continuar sem cache
        print(f"Cache error (continuando sem cache): {e}")
        pass
    
    # === CARDS DE MÉTRICAS ===
    total_chamados = chamados.count()
    chamados_produtivos = chamados.filter(produtiva=True).count()
    taxa_produtividade = (chamados_produtivos / total_chamados * 100) if total_chamados > 0 else 0
    
    # Calcular total de horas (convertendo TimeField para horas decimais)
    total_horas = 0
    for chamado in chamados:
        if chamado.total_horas:
            total_horas += chamado.total_horas.hour + chamado.total_horas.minute / 60
    
    # Chamados de hoje
    chamados_hoje = chamados.filter(data=date.today()).count()
    
    # === ALERTAS ===
    alertas = []
    if taxa_produtividade < 80:
        alertas.append({
            'tipo': 'warning',
            'mensagem': f'Taxa de produtividade baixa: {taxa_produtividade:.1f}%'
        })
    if chamados_hoje == 0:
        alertas.append({
            'tipo': 'info',
            'mensagem': 'Nenhum chamado registrado hoje'
        })
    if total_horas > 200:
        alertas.append({
            'tipo': 'success',
            'mensagem': f'Excelente produtividade: {total_horas:.1f}h trabalhadas'
        })
    
    # === GRÁFICO 1: Distribuição por Tipo de Atividade (Pizza) ===
    tipo_atividade_data = chamados.values('tipo_atividade').annotate(
        total=Count('id')
    ).order_by('-total')
    
    if tipo_atividade_data:
        fig_pizza = go.Figure(data=[go.Pie(
            labels=[item['tipo_atividade'] for item in tipo_atividade_data],
            values=[item['total'] for item in tipo_atividade_data],
            hole=0.4,
            marker=dict(
                colors=['#FFD700', '#FFA500', '#ffffff', '#cccccc', '#999999'],
                line=dict(color='white', width=2)
            ),
            textinfo='label+percent',
            textfont=dict(size=14, color='white'),
            hovertemplate='<b>%{label}</b><br>Chamados: %{value}<br>Percentual: %{percent}<extra></extra>'
        )])
        
        fig_pizza.update_layout(
            title={
                'text': 'Distribuição por Tipo de Atividade',
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 18, 'color': '#ffffff', 'family': 'Roboto'}
            },
            paper_bgcolor='rgba(26,26,26,0.95)',
            plot_bgcolor='rgba(26,26,26,0.95)',
            margin=dict(t=60, b=20, l=20, r=20),
            height=400,
            width=500,
            showlegend=True,
            legend=dict(
                orientation="v",
                yanchor="middle",
                y=0.5,
                xanchor="left",
                x=1.02,
                font=dict(size=11, color='#ffffff')
            )
        )
        grafico_pizza = fig_pizza.to_html(include_plotlyjs=False, div_id="grafico_pizza")
    else:
        grafico_pizza = "<p>Sem dados disponíveis</p>"
    
    # === GRÁFICO 2: Chamados por Analista (Barras Horizontais) ===
    analista_data = chamados.values('nome_analista__username').annotate(
        total=Count('id')
    ).order_by('-total')
    
    if analista_data:
        analistas = [item['nome_analista__username'].replace('_', ' ') for item in analista_data]
        totais = [item['total'] for item in analista_data]
        
        fig_barras = go.Figure(data=[go.Bar(
            y=analistas,
            x=totais,
            orientation='h',
            marker=dict(
                color=totais,
                colorscale=[[0, '#FFD700'], [1, '#FFA500']],
                line=dict(color='rgba(255,255,255,0.8)', width=1.5)
            ),
            text=totais,
            textposition='outside',
            textfont=dict(size=14, color='#ffffff'),
            hovertemplate='<b>%{y}</b><br>Total de Chamados: %{x}<extra></extra>'
        )])
        
        fig_barras.update_layout(
            title={
                'text': 'Chamados por Analista',
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 18, 'color': '#ffffff', 'family': 'Roboto'}
            },
            xaxis=dict(
                title='Quantidade de Chamados',
                showgrid=True,
                gridcolor='rgba(255,255,255,0.1)',
                title_font=dict(size=12, color='#ffffff'),
                tickfont=dict(color='#ffffff')
            ),
            yaxis=dict(
                title='',
                tickfont=dict(size=11, color='#ffffff')
            ),
            paper_bgcolor='rgba(26,26,26,0.95)',
            plot_bgcolor='rgba(26,26,26,0.95)',
            margin=dict(t=60, b=40, l=120, r=20),
            height=400,
            width=500
        )
        grafico_barras_analista = fig_barras.to_html(include_plotlyjs=False, div_id="grafico_barras_analista")
    else:
        grafico_barras_analista = "<p>Sem dados disponíveis</p>"
    
    # === GRÁFICO 3: Tempo Médio por Analista ===
    # Calcular tempo médio por analista manualmente (SQLite não suporta Avg em TimeField)
    chamados_por_analista = chamados.values('nome_analista__username', 'total_horas')
    
    if chamados_por_analista:
        # Organizar dados por analista
        dados_analistas = {}
        
        for item in chamados_por_analista:
            analista = item['nome_analista__username']
            horas = item['total_horas']
            
            if analista not in dados_analistas:
                dados_analistas[analista] = []
            
            if horas:
                # Converter TimeField para horas decimais
                horas_decimal = horas.hour + horas.minute / 60
                dados_analistas[analista].append(horas_decimal)
        
        # Calcular médias
        analistas = []
        tempos_medios = []
        
        for analista, horas_list in dados_analistas.items():
            if horas_list:
                media = sum(horas_list) / len(horas_list)
                analistas.append(analista.replace('_', ' '))
                tempos_medios.append(round(media, 2))
        
        # Ordenar por tempo médio (decrescente)
        dados_ordenados = sorted(zip(analistas, tempos_medios), key=lambda x: x[1], reverse=True)
        analistas = [item[0] for item in dados_ordenados]
        tempos_medios = [item[1] for item in dados_ordenados]
        
        fig_tempo_medio = go.Figure(data=[go.Bar(
            x=analistas,
            y=tempos_medios,
            marker=dict(
                color=tempos_medios,
                colorscale=[[0, '#FFD700'], [0.5, '#FFA500'], [1, '#ffffff']],
                line=dict(color='rgba(255,255,255,0.8)', width=1.5)
            ),
            text=[f'{h:.2f}h' for h in tempos_medios],
            textposition='outside',
            textfont=dict(size=14, color='#ffffff'),
            hovertemplate='<b>%{x}</b><br>Tempo Médio: %{y:.2f}h<extra></extra>'
        )])
        
        fig_tempo_medio.update_layout(
            title={
                'text': 'Tempo Médio por Analista',
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 20, 'color': '#ffffff', 'family': 'Roboto'}
            },
            xaxis=dict(
                title='Analista',
                showgrid=False,
                title_font=dict(size=14, color='#ffffff'),
                tickangle=-45,
                tickfont=dict(color='#ffffff')
            ),
            yaxis=dict(
                title='Tempo Médio (horas)',
                showgrid=True,
                gridcolor='rgba(255,255,255,0.1)',
                title_font=dict(size=14, color='#ffffff'),
                tickfont=dict(color='#ffffff')
            ),
            paper_bgcolor='rgba(26,26,26,0.95)',
            plot_bgcolor='rgba(26,26,26,0.95)',
            margin=dict(t=80, b=100, l=60, r=60),
            height=400
        )
        grafico_tempo_medio = fig_tempo_medio.to_html(include_plotlyjs=False, div_id="grafico_tempo_medio")
    else:
        grafico_tempo_medio = "<p>Sem dados disponíveis</p>"
    
    # === GRÁFICO 4: Tempo Médio Geral por Mês ===
    # Calcular tempo médio geral de todos os analistas por mês
    chamados_por_mes = chamados.annotate(
        mes=TruncMonth('data')
    ).values('mes', 'total_horas').order_by('mes')
    
    if chamados_por_mes:
        # Organizar dados por mês
        dados_meses = {}
        
        for item in chamados_por_mes:
            mes = item['mes']
            horas = item['total_horas']
            
            if mes not in dados_meses:
                dados_meses[mes] = []
            
            if horas:
                # Converter TimeField para horas decimais
                horas_decimal = horas.hour + horas.minute / 60
                dados_meses[mes].append(horas_decimal)
        
        # Calcular médias por mês
        meses = []
        medias_gerais = []
        
        for mes in sorted(dados_meses.keys()):
            horas_list = dados_meses[mes]
            if horas_list:
                media_geral = sum(horas_list) / len(horas_list)
                meses.append(mes)
                medias_gerais.append(round(media_geral, 2))
        
        fig_tempo_mes = go.Figure(data=[go.Bar(
            x=meses,
            y=medias_gerais,
            marker=dict(
                color=medias_gerais,
                colorscale=[[0, '#FFD700'], [0.5, '#FFA500'], [1, '#ffffff']],
                line=dict(color='rgba(255,255,255,0.8)', width=1.5)
            ),
            text=[f'{h:.2f}h' for h in medias_gerais],
            textposition='outside',
            textfont=dict(size=14, color='#ffffff'),
            hovertemplate='<b>%{x}</b><br>Tempo Médio Geral: %{y:.2f}h<extra></extra>'
        )])
        
        # Formatar labels do eixo X para mostrar apenas mês/ano
        meses_formatados = []
        for mes in meses:
            # Converter para string no formato "Mês/Ano"
            mes_str = mes.strftime('%b/%Y')  # Ex: "Aug/2025", "Sep/2025"
            meses_formatados.append(mes_str)
        
        fig_tempo_mes.update_layout(
            title={
                'text': 'Tempo Médio Geral por Mês',
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 20, 'color': '#ffffff', 'family': 'Roboto'}
            },
            xaxis=dict(
                title='Mês',
                showgrid=False,
                title_font=dict(size=14, color='#ffffff'),
                tickangle=-45,
                tickmode='array',
                tickvals=meses,
                ticktext=meses_formatados,
                tickfont=dict(color='#ffffff')
            ),
            yaxis=dict(
                title='Tempo Médio (horas)',
                showgrid=True,
                gridcolor='rgba(255,255,255,0.1)',
                title_font=dict(size=14, color='#ffffff'),
                tickfont=dict(color='#ffffff')
            ),
            paper_bgcolor='rgba(26,26,26,0.95)',
            plot_bgcolor='rgba(26,26,26,0.95)',
            margin=dict(t=80, b=100, l=60, r=60),
            height=400
        )
        grafico_tempo_mes = fig_tempo_mes.to_html(include_plotlyjs=False, div_id="grafico_tempo_mes")
    else:
        grafico_tempo_mes = "<p>Sem dados disponíveis</p>"
    
    # Preparar contexto
    context = {
        'total_chamados': total_chamados,
        'chamados_hoje': chamados_hoje,
        'taxa_produtividade': round(taxa_produtividade, 1),
        'total_horas': round(total_horas, 1),
        'grafico_pizza': grafico_pizza,
        'grafico_barras_analista': grafico_barras_analista,
        'grafico_tempo_medio': grafico_tempo_medio,
        'grafico_tempo_mes': grafico_tempo_mes,
        'alertas': alertas,
        'periodo_atual': periodo,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
    }
    
    # Salvar no cache por 15 minutos (se possível)
    try:
        from django.conf import settings
        cache.set(cache_key, context, settings.CACHE_TTL)
    except Exception as e:
        # Se o cache falhar, continuar sem salvar
        print(f"Cache save error (continuando sem salvar no cache): {e}")
        pass
    
    return render(request, 'dashboard.html', context)


def exportar_pdf(request):
    """
    Exportar relatório do dashboard em PDF
    """
    # Aplicar os mesmos filtros do dashboard
    periodo = request.GET.get('periodo', 'todos')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    
    chamados = Chamados.objects.all()
    
    if periodo == 'semana':
        data_inicio = date.today() - timedelta(days=7)
        data_fim = date.today()
    elif periodo == 'mes':
        data_inicio = date.today() - timedelta(days=30)
        data_fim = date.today()
    elif periodo == 'ano':
        data_inicio = date.today() - timedelta(days=365)
        data_fim = date.today()
    elif data_inicio and data_fim:
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
    
    if periodo != 'todos':
        chamados = chamados.filter(data__range=[data_inicio, data_fim])
    
    # Calcular métricas
    total_chamados = chamados.count()
    chamados_produtivos = chamados.filter(produtiva=True).count()
    taxa_produtividade = (chamados_produtivos / total_chamados * 100) if total_chamados > 0 else 0
    
    total_horas = 0
    for chamado in chamados:
        if chamado.total_horas:
            total_horas += chamado.total_horas.hour + chamado.total_horas.minute / 60
    
    # Criar PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="relatorio_dashboard_{periodo}_{date.today()}.pdf"'
    
    doc = SimpleDocTemplate(response, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=1,  # Center
        textColor=colors.HexColor('#667eea')
    )
    story.append(Paragraph("📊 Relatório de Dashboard - Análise de Chamados", title_style))
    story.append(Spacer(1, 20))
    
    # Informações do período
    periodo_text = f"Período: {periodo.title()}"
    if data_inicio and data_fim:
        periodo_text += f" ({data_inicio} a {data_fim})"
    
    story.append(Paragraph(periodo_text, styles['Normal']))
    story.append(Paragraph(f"Data de geração: {date.today()}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Métricas principais
    story.append(Paragraph("📈 Métricas Principais", styles['Heading2']))
    
    metrics_data = [
        ['Métrica', 'Valor'],
        ['Total de Chamados', str(total_chamados)],
        ['Chamados Produtivos', str(chamados_produtivos)],
        ['Taxa de Produtividade', f"{taxa_produtividade:.1f}%"],
        ['Total de Horas', f"{total_horas:.1f}h"],
    ]
    
    metrics_table = Table(metrics_data)
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(metrics_table)
    story.append(Spacer(1, 20))
    
    # Análise por tipo de atividade
    story.append(Paragraph("📋 Análise por Tipo de Atividade", styles['Heading2']))
    
    tipo_data = chamados.values('tipo_atividade').annotate(
        total=Count('id'),
        produtivas=Count('id', filter=Q(produtiva=True)),
        nao_produtivas=Count('id', filter=Q(produtiva=False))
    ).order_by('-total')
    
    tipo_table_data = [['Tipo de Atividade', 'Total', 'Produtivas', 'Não Produtivas', 'Taxa (%)']]
    
    for item in tipo_data:
        taxa = (item['produtivas'] / item['total'] * 100) if item['total'] > 0 else 0
        tipo_table_data.append([
            item['tipo_atividade'],
            str(item['total']),
            str(item['produtivas']),
            str(item['nao_produtivas']),
            f"{taxa:.1f}%"
        ])
    
    tipo_table = Table(tipo_table_data)
    tipo_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#764ba2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(tipo_table)
    story.append(Spacer(1, 20))
    
    # Análise por analista
    story.append(Paragraph("👥 Análise por Analista", styles['Heading2']))
    
    analista_data = chamados.values('nome_analista__username').annotate(
        total=Count('id'),
        produtivas=Count('id', filter=Q(produtiva=True))
    ).order_by('-total')
    
    analista_table_data = [['Analista', 'Total', 'Produtivas', 'Taxa (%)', 'Tempo Médio']]
    
    # Calcular tempo médio manualmente para cada analista
    for item in analista_data:
        taxa = (item['produtivas'] / item['total'] * 100) if item['total'] > 0 else 0
        
        # Buscar chamados do analista para calcular tempo médio
        analista_username = item['nome_analista__username']
        chamados_analista = chamados.filter(nome_analista__username=analista_username)
        
        tempo_medio = 0
        horas_totais = []
        for chamado in chamados_analista:
            if chamado.total_horas:
                horas = chamado.total_horas.hour + chamado.total_horas.minute / 60
                horas_totais.append(horas)
        
        if horas_totais:
            tempo_medio = sum(horas_totais) / len(horas_totais)
        
        analista_table_data.append([
            item['nome_analista__username'].replace('_', ' '),
            str(item['total']),
            str(item['produtivas']),
            f"{taxa:.1f}%",
            f"{tempo_medio:.2f}h"
        ])
    
    analista_table = Table(analista_table_data)
    analista_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#43e97b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(analista_table)
    
    # Gerar PDF
    doc.build(story)
    return response


def dashboard_personalizado(request, user_id):
    """
    Dashboard personalizado para um usuário específico
    """
    try:
        usuario = User.objects.get(id=user_id)
        chamados_usuario = Chamados.objects.filter(nome_analista=usuario)
        
        # Aplicar filtros se fornecidos
        periodo = request.GET.get('periodo', 'todos')
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')
        
        if periodo == 'semana':
            data_inicio = date.today() - timedelta(days=7)
            data_fim = date.today()
        elif periodo == 'mes':
            data_inicio = date.today() - timedelta(days=30)
            data_fim = date.today()
        elif periodo == 'ano':
            data_inicio = date.today() - timedelta(days=365)
            data_fim = date.today()
        elif data_inicio and data_fim:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        
        if periodo != 'todos':
            chamados_usuario = chamados_usuario.filter(data__range=[data_inicio, data_fim])
        
        # Métricas do usuário
        total_chamados = chamados_usuario.count()
        chamados_produtivos = chamados_usuario.filter(produtiva=True).count()
        taxa_produtividade = (chamados_produtivos / total_chamados * 100) if total_chamados > 0 else 0
        
        total_horas = 0
        for chamado in chamados_usuario:
            if chamado.total_horas:
                total_horas += chamado.total_horas.hour + chamado.total_horas.minute / 60
        
        context = {
            'usuario': usuario,
            'total_chamados': total_chamados,
            'chamados_produtivos': chamados_produtivos,
            'taxa_produtividade': round(taxa_produtividade, 1),
            'total_horas': round(total_horas, 1),
            'periodo_atual': periodo,
            'data_inicio': data_inicio,
            'data_fim': data_fim,
        }
        
        return render(request, 'dashboard_personalizado.html', context)
        
    except User.DoesNotExist:
        return render(request, 'dashboard.html', {'error': 'Usuário não encontrado'})

      
   

    
        
      
        

