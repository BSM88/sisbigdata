from dash.dependencies import Output, Input, State
import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html
import plotly.express as px
from flask import Flask
import pandas as pd
import dash

from pandas import json_normalize
import requests
import numpy as np

server = Flask(__name__)
app = dash.Dash(server=server, external_stylesheets=[dbc.themes.FLATLY])
app.title = 'Dashboard'

username = xxxx
password = 'xxxx'
session = requests.Session()


# engine = create_engine("mysql+pymysql://" + 'sistemesbd' + ":" + 'bigdata2223' + "@" + '192.168.193.133:3306' + "/" + 'alumnes')

def tables_df(username,password):

    urlTablas = f'https://services.informa.es/api/get-tables?username={username}&password={password}&idioma=es'
    r = session.get(urlTablas)
    jsons=r.json()

    for i,j in enumerate(jsons['datosProducto']['tablaDeLiterales']):
        js = jsons['datosProducto']['tablaDeLiterales'][j]
        df = json_normalize(js)
        df1_transposed = df.T
        df1_transposed.reset_index(inplace = True)
        df1_transposed.columns =['code', 'description']
        df1_transposed['table'] = j

        if i == 0:
            tables_df = df1_transposed
        else:
            tables_df = pd.concat([tables_df,df1_transposed])
    
    return tables_df

def Xls_codesScope(mappingCodes):
    codesScope = []
    for n in mappingCodes['code'].iteritems():
        codesScope.append(n[1])
    return codesScope

def dfPartidas(listaPartidas, codesScope):
    cogigosPartida = []
    codes = []
    valores = []
    tabla_codificacion = []
    
    for enump, p in enumerate(listaPartidas):
        cogigosPartida.append(p['codigoPartida'])
        codes.append(p['campoCodificadoPartidaConPlantilla']['valor'])
        tabla_codificacion.append(p['campoCodificadoPartidaConPlantilla']['tablaDecodificacion'])
        valores.append(p['valor'])
    Balances_df = pd.DataFrame(list(zip(cogigosPartida,codes, valores,tabla_codificacion)),
    columns =['codigo_partida','code', 'valor','tabla_codigo'])
    
    if len(codesScope) > 0:
        Balances_df = Balances_df.loc[Balances_df.code.isin(codesScope)]
    

    return Balances_df

def add_row(new_row, df):
    new_row = pd.DataFrame(new_row, index=[0])
    new_df = pd.concat([new_row,df.loc[:]]).reset_index(drop = True)
    return new_df

def rows_Profitability(Balances_df_all):
    group = Balances_df_all.loc[Balances_df_all['New Account'].isin(['Income RAC (k€)',"Income Other (k€)",'EBT (k€)'])]
    pivot = pd.pivot_table(group, 
                           values="Amount (K€)", 
                           index=["nif","empresa","year"], 
                           columns="New Account",
                           aggfunc='sum',
                           )
    pivot['Profitability'] = pivot['EBT (k€)']/(pivot["Income Other (k€)"] + pivot["Income RAC (k€)"])        
    pivot = pivot.loc[:, ['Profitability']]
    pivot.reset_index(inplace = True)
    unpivot = pd.melt(pivot, id_vars=["nif","empresa","year"], value_vars=['Profitability'])
    unpivot = unpivot.rename(columns={'value': 'Amount (K€)'})  
    unpivot['valor'] = unpivot['Amount (K€)']
    Balances_df_all = pd.concat([Balances_df_all,unpivot])
    return Balances_df_all

def balances_df(nifsList, codes):
   
    listas_cuentas = ['listaPartidasBalanceActivo','listaPartidasBalancePasivo','listaPartidasCuentaPerdidasGanancias']
    product = 'INFORME_MAYOR'
    
    for enumn, n in enumerate(nifsList):
# for enumn, n in enumerate(['B07947591']):
#     print(n)

    #codesScope = []
        url = f'https://services.informa.es/api/get-product?username={username}&password={password}&product={product}&cif={n}'
        r = session.get(url)
        jsons=r.json()
        jsons

        listaBalances = jsons['datosProducto']['informacionFinanciera']['listaBalances']

        for enumb, b in enumerate(listaBalances):

            annoBalance = b['cabeceraBalance']['annoBalance']
            if 'numeroTotalEmpleados' in b['cabeceraBalance']:
                numEmpleados = b['cabeceraBalance']['numeroTotalEmpleados']
            else: 
                numEmpleados=0
            for enumc, c in enumerate(listas_cuentas):
                listaPartidas = b[c]
                Balances_df = dfPartidas(listaPartidas, codes)

                Balances_df['Concepto'] = c
                Balances_df['year'] = annoBalance
                Balances_df['nif']=n

                if ((enumc == 0) & (enumb == 0) & (enumn == 0)):
                    Balances_df_all = Balances_df
                else:
                    Balances_df_all = pd.concat([Balances_df_all,Balances_df]) 

            new_row = {'code': 'Nº of employees', 'nif': n, 'year': annoBalance, 'valor':numEmpleados}
            Balances_df_all = add_row(new_row, Balances_df_all)

    return Balances_df_all

def balances_df_all(Balances_df):
    Balances_df['Origen'] = Balances_df.Concepto
    Balances_df['Origen'] = Balances_df.Origen.str.replace('listaPartidasBalanceActivo','Balance - Activo')
    Balances_df['Origen'] = Balances_df.Origen.str.replace('listaPartidasBalancePasivo','Balance - Pasivo')
    Balances_df['Origen'] = Balances_df.Origen.str.replace('listaPartidasCuentaPerdidasGanancias','PyG')
    
    Balances_df_all = Balances_df.merge(tables_df, left_on='code', right_on='code', how='left')
    Balances_df_all = Balances_df_all.merge(nifsDf, left_on='nif', right_on='NIF', how='left')
    Balances_df_all = Balances_df_all.merge(mappingCodes, left_on='code', right_on='code', how='left')
    Balances_df_all['Amount (K€)']= np.where((Balances_df_all.Escala.isnull()) & (Balances_df_all.code != 'Nº of employees'), Balances_df_all.valor/1000, Balances_df_all.valor)
    # Balances_df_all['Amount (K€)']= np.where(Balances_df_all.Escala.isnull(), Balances_df_all.valor/1000, Balances_df_all.valor)
    Balances_df_all = Balances_df_all.loc[:, ['Origen','nif','empresa','year','codigo_partida','code','description_x','valor','Escala','New Account','Amount (K€)']]
    Balances_df_all = Balances_df_all.rename(columns={'description_x': 'description'})   
    Balances_df_all = rows_Profitability(Balances_df_all)
    return Balances_df_all

tables_df = tables_df(username,password)


nifsDf_json = '{"empresa":{"0":"ALPHACITY","1":"ALQUIBER QUALITY SA","2":"AMOVENS","3":"ANDACAR 2000 SA","4":"AVIS","5":"CAR2GO","6":"CELERING","7":"CENTAURO","8":"CICAR + CABRERA MEDINA","9":"CICAR + CABRERA MEDINA","10":"CLICKCAR","11":"COVEY","12":"DISFRIMUR SERVICIOS SL","13":"DOMINGO ALONSO","14":"DRIVALIA","15":"EMOV \\/ FREE2MOVE","16":"ENTERPRISE","17":"EUROPCAR","18":"FURGOLINE","19":"FURGONETAS DEMETRIO SL","20":"GETAROUND","21":"GOLDCAR","22":"GUPPY","23":"HERTZ","24":"HI MOBILITY","25":"IBILKARI","26":"OK MOBILITY ESPA\\u00d1A","27":"OK MOBILITY ESPA\\u00d1A","28":"OK RENT A CAR","29":"PROA","30":"RECORD GO","31":"RESPIRO","32":"SIXT","33":"TELEFURGO SL","34":"Ubeeqo \\/ Blue Sostenible","35":"ULTRAMAR CAR","36":"WIBLE","37":"ZITY \\/ CARSHARING"},"NIF":{"0":"A91001438","1":"A09373861","2":"B85636579","3":"A12363529","4":"A28152767","5":"B87267498","6":"B88056866","7":"B03965506","8":"B35051820","9":"B35102144","10":"B95604765","11":"B29733870","12":"B73015661","13":"B35938893","14":"B54509971","15":"A87657086","16":"A28047884","17":"A28364412","18":"A12988887","19":"B53390480","20":"B87335725","21":"B03403169","22":"B33608704","23":"B28121549","24":"B33886367","25":"B75001750","26":"B57334609","27":"B57854168","28":"B57334757","29":"B07554769","30":"A12584470","31":"B85607703","32":"B07947591","33":"B84591759","34":"B86038064","35":"B57315517","36":"B88054176","37":"B87908513"},"Escala":{"0":null,"1":null,"2":null,"3":null,"4":null,"5":null,"6":null,"7":null,"8":null,"9":null,"10":null,"11":null,"12":null,"13":null,"14":null,"15":null,"16":null,"17":"K \\u20ac","18":null,"19":null,"20":null,"21":"K \\u20ac","22":null,"23":"K \\u20ac","24":null,"25":null,"26":null,"27":null,"28":null,"29":null,"30":null,"31":null,"32":null,"33":null,"34":null,"35":"K \\u20ac","36":null,"37":"K \\u20ac"}}'
nifsDf =pd.read_json(nifsDf_json)
mappingCodes_json = '{"New Account":{"0":"Income RAC (k\\u20ac)","1":"Income Other (k\\u20ac)","2":"Income Other (k\\u20ac)","3":"EBT (k\\u20ac)","4":"Total assets (k\\u20ac)","5":"Equity (k\\u20ac)","6":"N\\u00ba of employees","7":"Income RAC (k\\u20ac)","8":"EBT (k\\u20ac)"},"description":{"0":"b) Prestaciones de servicios","1":"5. Otros ingresos de explotaci\\u00f3n","2":"a) Ventas","3":"A.3) RESULTADO ANTES DE IMPUESTOS (A.1 + A.2)","4":"TOTAL ACTIVO (A + B)","5":"A-1) Fondos propios","6":"N\\u00ba of employees","7":"1. Importe neto de la cifra de negocios","8":"C)  RESULTADO ANTES DE IMPUESTOS (A + B)"},"code":{"0":"40120GN","1":"40500GN","2":"40110GN","3":"4930013","4":"10000GN","5":"21000GN","6":"N\\u00ba of employees","7":"40100GN","8":"49300GN"}}'
mappingCodes =pd.read_json(mappingCodes_json)
mappingCodes
codesScope=Xls_codesScope(mappingCodes)
nifsList = ['B07947591','A28364412','B03403169','B57315517','B28121549','B07554769','A28152767','B35938893','A28047884','A12584470']
nifsList.sort()

codes = codesScope
Balances_df = balances_df(nifsList,codes)
Balances_df

Balances_df_all_Short = balances_df_all(Balances_df)
Balances_df_all_Short

# ---------------DROPDOWN LISTS

years = Balances_df_all_Short.year.unique()
years.sort()
yearSelector=[]
for c in years:
    yearSelector.append({'label':c,'value':c})
yearSelector

nifSelector = []
for c in nifsList:
    nifSelector.append({'label':c,'value':c})
nifSelector

kpis = Balances_df_all_Short["New Account"].unique()
kpiSelector = []
for c in kpis:
    kpiSelector.append({'label':c,'value':c})
kpiSelector

nifSelectorFirstValue = nifsList
yearSelectorFirstValue = 2021
kpiSelectorFirstValue = 'Income RAC (k€)'


selectorNif = dcc.Dropdown(id='nifSelectorId', options=nifSelector,value= nifSelectorFirstValue,multi=True, 
                className='nifselector',style={'width':'1200px'},placeholder="Selecciona un indicador" )

selectorYear = dcc.Dropdown(id='yearSelectorId', options=yearSelector,value= yearSelectorFirstValue,multi=False, 
                className='yearselector',style={'width':'300px'},placeholder="Selecciona un indicador" )

selectorKpi = dcc.Dropdown(id='kpiSelectorId', options=kpiSelector,value= kpiSelectorFirstValue, multi=False, 
                className='kpiselector',style={'width':'300px'},placeholder="Selecciona un indicador" )


#######  PIE MARKET SHARE ##########
year = yearSelectorFirstValue
msdf = Balances_df_all_Short[
                                (Balances_df_all_Short["New Account"] == 'Income RAC (k€)') & 
                                (Balances_df_all_Short["year"] == year)
                               ].groupby(['empresa','year']).sum()
msdf.reset_index(inplace=True)


mspie=dbc.Alert([html.H5("Market Share", className="alert-heading"),
    selectorYear,
    html.Br(),
    dcc.Graph(id='mspie',
        figure = px.pie(msdf, values='Amount (K€)', names= 'empresa', title= f'Market Share in {year}')
        )
    ])

#######  KPI TIMELINE ##########

kpi = kpiSelectorFirstValue

kpidf = Balances_df_all_Short[(Balances_df_all_Short["New Account"] == kpi)].groupby(['empresa','year']).sum()
kpidf.reset_index(inplace=True)
kpidf

if kpi == 'Profitability':
    yaxes = '%'
elif kpi == 'Nº of employees':
    yaxes = 'FTE\'s'
else:
    yaxes = 'Amount (K€)'

fig = px.line(kpidf, x="year", y="Amount (K€)", color='empresa',title= f'{kpi} Timeline Chart')
fig.update_xaxes(title_text='Year')
fig.update_yaxes(title_text=yaxes)

fig.update_layout(
   xaxis = dict(
      tickmode = 'linear',
      tick0 = 2018,
      dtick = 1
   )
)


    
kpitl=dbc.Alert([html.H5("Timeline", className="alert-heading"),
    selectorKpi,
    html.Br(),

    dcc.Graph(id='kpitl', 
        figure = fig
        )
    ])


titulo = dbc.NavbarBrand("Competitors Dashboard", className="ms-2",style={'textAlign': 'center','height':'40px','color': 'black', 'font-weight': 'bold'})

navbar = dbc.Navbar(dbc.Row([
            dbc.Col(dbc.Row([titulo,selectorNif]),width=3),
            ]),
    color="orange",
    dark=True
)

app.layout =  html.Div(children=[
    navbar,
    html.Br(),
       dbc.Row([
            dbc.Col(html.Div([mspie]),width=5),
            dbc.Col(html.Div([kpitl]),width=7) 
            ]),
            dbc.Row([
          dbc.Col(html.Div([dbc.Alert("BSM", color="dark")]),width=12)
    ])
    ])

# app.layout =  dbc.Container([ 
#                 dbc.Row([
#             dbc.Col(html.Div([mspie]),width=5),
#             dbc.Col(html.Div([kpitl]),width=7) 
#             ]),
          
# ])
    
@app.callback(
    Output('mspie', 'figure'),
    [Input('yearSelectorId', 'value')]
    )

def update_graph(selected_year):

    msdf = Balances_df_all_Short[
                                (Balances_df_all_Short["New Account"] == 'Income RAC (k€)') & 
                                (Balances_df_all_Short["year"] == selected_year)
                               ].groupby(['empresa','year']).sum()
    msdf.reset_index(inplace=True)
    mspie= px.pie(msdf, values='Amount (K€)', names= 'empresa', title= f'Market Share in {selected_year}')

    return mspie

@app.callback(
    Output('kpitl', 'figure'),
    [Input('kpiSelectorId', 'value')]
    )

def update_graph(selected_kpi):
    kpidf = Balances_df_all_Short[(Balances_df_all_Short["New Account"] == selected_kpi)].groupby(['empresa','year']).sum()
    kpidf.reset_index(inplace=True)
    kpidf

    if selected_kpi == 'Profitability':
        yaxes = '%'
    elif selected_kpi == 'Nº of employees':
        yaxes = 'FTE\'s'
    else:
        yaxes = 'Amount (K€)'

    fig = px.line(kpidf, x="year", y="Amount (K€)", color='empresa',title= f'{selected_kpi} Timeline Chart')
    fig.update_xaxes(title_text='Year')
    fig.update_yaxes(title_text=yaxes)

    fig.update_layout(
       xaxis = dict(
          tickmode = 'linear',
          tick0 = 2018,
          dtick = 1
       )
    )

    return fig

    
if __name__=='__main__':
    app.run_server()
