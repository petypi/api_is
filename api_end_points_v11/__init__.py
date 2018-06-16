import json
import re
import logging
import string
import traceback
import configparser
import os

from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_basicauth import BasicAuth
from .lib.api import API as API
from .queue_manager import DataProvisionClient

app = Flask(__name__)
api = API()

_config_parser = configparser.ConfigParser()
_config_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '.', 'settings.ini'))
_config_parser.read(_config_file)

app.config['BASIC_AUTH_USERNAME'] = _config_parser.get('api', 'username')
app.config['BASIC_AUTH_PASSWORD'] = _config_parser.get('api', 'password')

basic_auth = BasicAuth(app)


@app.route('/app_version', methods=['POST'])
@basic_auth.required
def app_Version():
    '''
    Check if the current app is the right version
    :return:
    True if versions are same else false
    '''

    package_name = request.form['package_name'].strip()
    version = request.form['version'].strip()
    try:
        res = api.do_kw("copia.android.app", "search_count",
                        [[('package_name', '=', package_name), ('version', '<=', float(version))]])

        if res:
            response = format_output(0, True, None)
        else:
            response = format_output(10, False, "Update Application")
    except Exception as error:
        print(traceback.format_exc(error))
        response = format_output(10, None, "Something went wrong try again. If issue persists contact Administrator")
    return jsonify(response)


####################################### Logistics ##########################################################
@app.route('/products/<write_date>', methods=['GET'])
@basic_auth.required
def get_products(write_date):
    '''
    Gets products from erp that have been modified after a specific start date
    :return:
    '''
    try:
        date = datetime.strptime(write_date.replace("-", "/"), "%d/%m/%Y %H:%M:%S")
        date = date - timedelta(hours=3)
        date = date.strftime("%m/%d/%Y %H:%M:%S")
        if len(write_date) == 0:
            res = api.do('product.product', 'search_read',
                         ['|', ['active', '=', True], ['active', '=', False], ['default_code', '!=', False],
                          ['write_date', '>=', "01/01/2000 00:00"]],
                         ['name', ])
        else:
            res = api.do('product.product', 'search_read',
                         ['|', ['active', '=', True], ['active', '=', False], ['default_code', '!=', False],
                          ['write_date', '>=', date]], ['name'])

        if res:
            response = format_output(0, res, None)
        else:
            response = format_output(10, None, "No Products to sync")
    except Exception as error:
        print(traceback.format_exc(error))
        response = format_output(10, None, "Something went wrong try again. If issue persists contact Administrator")
    return jsonify(response)


@app.route('/region_names', methods=['GET'])
@basic_auth.required
def get_region_names():
    '''
    Gets Region Info from erp
    :return:
    '''
    region_ids = api.do("delivery.region", "search", [])
    try:
        res = api.do("delivery.region", "read", region_ids,
                     ['name', 'route_ids', 'ofs_url', 'ofs_url_secondary', 'ofs_db', 'ofs_username', 'ofs_password'])

        if res:
            for region in res:
                region['routes'] = _get_route_names(region['route_ids']) or []

            response = format_output(0, res, None)
        else:
            response = format_output(10, None, "No Region IDs to sync")
    except Exception as error:
        print(traceback.format_exc(error))
        response = format_output(10, None, "Something went wrong try again. If issue persists contact Administrator")
    return jsonify(response)


def _get_route_names(route_ids):
    return api.do("delivery.route", "read", route_ids, ['route_name']) or False


@app.route('/users', methods=['GET'])
@basic_auth.required
def get_users():
    '''
    Gets Region names when provided with a region_id list
    :return:
    '''
    try:
        res = api.do("logistics.user", "search_read", [], ['name', 'phone', 'alternate_phone', 'pin', 'user_type'])

        if res:

            for user in res:
                _update_logistics_response(user)
            response = format_output(0, res, None)
        else:
            response = format_output(10, None, "No Region IDs to sync")
    except Exception as error:
        print(traceback.format_exc(error))
        response = format_output(10, None, "Something went wrong try again. If issue persists contact Administrator")
    return jsonify(response)


def _update_logistics_response(user):
    user['login'] = user['phone']
    user['groups'] = [{'name': user['user_type']}]
    user.pop('user_type', None)


@app.route('/commit_to_ofs', methods=['POST'])
@basic_auth.required
def commit_to_ofs():
    '''
    Gets agent commissions from erp
    :return:
    '''

    container_ref = request.form['container_ref']
    verified_by = request.form['verified_by']
    receipt_refs = json.loads(request.form['receipt_refs'])
    ofs_db = request.form['ofs_db']
    ofs_user = request.form['ofs_user']
    ofs_pass = request.form['ofs_pass']
    ofs_url_res = request.form['ofs_url']
    ofs_url = ofs_url_res.split(':')[1].replace("/", "")
    ofs_port = ofs_url_res.split(':')[2].replace("/", "")

    _logger = logging.getLogger("Legacy API")
    _logger.warn('responses %s /\n ofs_url %s \n ofs_port %s \n ofs_db %s \n ofs_user %s \n ofs_pass %s' % (
        ofs_url_res, ofs_url, ofs_port, ofs_db, ofs_user, ofs_pass))
    try:
        _api = API().init(ofs_url, ofs_port, ofs_db, ofs_user, ofs_pass)

        res = _api.commit_to_ofs("delivery.receipt", "pack_order", container_ref, verified_by, receipt_refs)

        if res:

            if "success" in res:
                response = format_output(0, res['success'], None)
            elif "error" in res:
                response = format_output(10, res['error'], None)
        else:
            response = format_output(10, None, "No response from server")
    except Exception as error:
        print(traceback.format_exc(error))
        response = format_output(10, None, "Something went wrong try again. If issue persists contact administrator")
    return jsonify(response)


@app.route('/ofs_receive_dispatch', methods=['POST'])
@basic_auth.required
def ofs_receive_dispatch():
    '''
    OFS receive dispatch
    :return:
    '''

    container_refs = request.form['container_refs']
    delivery_date = request.form['delivery_date']
    ofs_db = request.form['ofs_db']
    ofs_user = request.form['ofs_user']
    ofs_pass = request.form['ofs_pass']
    ofs_url_res = request.form['ofs_url']
    ofs_url = ofs_url_res.split(':')[1].replace("/", "")
    ofs_port = ofs_url_res.split(':')[2].replace("/", "")

    try:
        _api = API().init(ofs_url, ofs_port, ofs_db, ofs_user, ofs_pass)

        res = _api.ofs_receive_dispatch("dispatch.order", "receive_dispatch", container_refs, delivery_date)

        res = res.__str__()
        if "True" in res:
            response = format_output(0, res, None)
        elif "Error" in res:
            response = format_output(10, res, None)
        else:
            response = format_output(10, None, "No response from server")
    except Exception as error:
        print(traceback.format_exc(error))
        response = format_output(10, None,
                                 "Something went wrong try again. If issue persists contact administrator")
    return jsonify(response)


@app.route('/ofs_return_box', methods=['POST'])
@basic_auth.required
def ofs_return_box():
    '''
    Process OFS return boxes
    :return:
    '''

    container_refs = request.form['container_refs']
    delivery_date = request.form['delivery_date']
    ofs_db = request.form['ofs_db']
    ofs_user = request.form['ofs_user']
    ofs_pass = request.form['ofs_pass']
    ofs_url_res = request.form['ofs_url']
    ofs_url = ofs_url_res.split(':')[1].replace("/", "")
    ofs_port = ofs_url_res.split(':')[2].replace("/", "")

    try:
        _api = API().init(ofs_url, ofs_port, ofs_db, ofs_user, ofs_pass)

        res = _api.ofs_return_box("dispatch.order", "return_box", container_refs)

        if res:
            response = format_output(0, res, None)
        else:
            response = format_output(10, None, "No response from server")
    except Exception as error:
        print(traceback.format_exc(error))
        response = format_output(10, None,
                                 "Something went wrong try again. If issue persists contact administrator")
    return jsonify(response)


##########################################################################################################

####################################### Ecat 2.0 ##########################################################
@app.route('/agent_commissions', methods=['POST'])
@basic_auth.required
def get_agent_commission():
    '''
    Gets agent commissions from erp
    :return:
    '''

    erp_id = request.form['erpId']
    erp_id = int(erp_id)
    start_date = request.form['startDate']
    end_date = request.form['endDate']
    try:
        res = api.do_new("res.partner", "action_get_agent_commission", [erp_id],
                         {"start_date": start_date, "end_date": end_date})

        if res:
            res = res.get(str(erp_id), None)
            response = format_output(0, res, None)
        else:
            response = format_output(10, None, "No commissions found")
    except Exception as error:
        print(traceback.format_exc(error))
        response = format_output(10, None, "Something went wrong try again. If issue persists contact administrator")
    return jsonify(response)


@app.route('/customer_report', methods=['POST'])
@basic_auth.required
def get_customer_report():
    '''
   get customer report from database
    :return:
    '''
    erp_id = request.form['erpid']
    erp_id = int(erp_id)
    try:
        customers = api.do("res.partner", "search_read", [('agent_id', '=', erp_id)], ['name', 'phone', 'mobile'])
        res = api.do_kw('sale.order', 'search_read', [[('customer_id', 'in', [x.get('id', None) for x in customers])]],
                        {'fields': ['create_date', 'name', 'amount_total', 'customer_id'],
                         'order': 'create_date desc'})

        if res:
            response = format_output(0, _format_customer_report(res, customers), None)
        else:
            response = format_output(10, None, "No customer report found")
    except Exception as error:
        print(traceback.format_exc(error))
        response = format_output(10, None, "Something went wrong try again. If issue persists contact administrator")
    return jsonify(response)


def _format_customer_report(data, customers):
    res = []
    for report in data:
        phone = [x.get('phone', None) for x in customers if x.get('id') == report['customer_id'][0]][0]
        mobile = [x.get('mobile', None) for x in customers if x.get('id') == report['customer_id'][0]][0]
        res.append({"order_date": report['create_date'],
                    "amount": report['amount_total'],
                    "id": report['id'],
                    "last_order": report['name'],
                    "customer_id": report['customer_id'][0],
                    "cust_name": report['customer_id'][1],
                    "phone": phone if phone else None,
                    "mobile": mobile if mobile else None,
                    })

    response = []
    for customer in customers:
        response.append(_get_last_order(customer, res))

    return response


def _get_last_order(customer, data):
    for report in data:
        if report.get('customer_id') == customer.get('id'):
            return report


@app.route('/sa_orders/<int:is_sale>/<int:erp_id>/<string:date_from>/<string:date_to>', methods=['GET'])
@basic_auth.required
def get_sales_orders(is_sale, erp_id, date_from, date_to):
    """
    Get sale orders for agents under a rep
    :return:
    """
    # get agents under the sales rep
    if is_sale == 0:
        agent_ids = api.do('res.partner', 'search',
                           [('sale_associate_id', '=', erp_id)])
    else:
        agent_ids = [erp_id]

    # format date from
    date_from = datetime.strptime(date_from.replace("-", "/"), "%d/%m/%Y")
    date_from = date_from - timedelta(hours=3)
    date_from = date_from.strftime("%m/%d/%Y %H:%M:%S")

    # format date to
    date_to = datetime.strptime(date_to.replace("-", "/"), "%d/%m/%Y")
    date_to = date_to + timedelta(hours=21)
    date_to = date_to.strftime("%m/%d/%Y %H:%M:%S")

    # Get sale orders of all agents under the sales associate
    # sale_order_ids = _get_agent_orders(agent_ids, date_from, date_to)

    try:
        if is_sale != 0:
            res = api.do("sale.order", "search_read", [('partner_id', '=', agent_ids),
                                                       ('create_date', '>=', date_from),
                                                       ('create_date', '<=', date_to)],
                         ['name', 'state', 'amount_total', 'create_date', 'partner_id'])
        else:
            res = api.do("sale.order", "search_read",
                         ['|', ('partner_id', '=', agent_ids), ('sale_associate_id', '=', erp_id),
                          ('create_date', '>=', date_from),
                          ('create_date', '<=', date_to)],
                         ['name', 'state', 'amount_total', 'create_date', 'partner_id'])
        res = _format_so_response(res)

        if res:
            response = format_output(0, res, None)
        else:
            response = format_output(10, None, "No Sales Orders for this period")
    except Exception as error:
        print(traceback.format_exc(error))
        response = format_output(10, None, "Something went wrong try again. If issue persists contact administrator")
    return jsonify(response)


def _format_so_response(sale_orders):
    """
    :param sale_orders: Gets a list of sale orders for a particular sales associate
    :return:  formatted response of a list of sale orders for agents under the sale associate
    """
    res = []
    for sale_order in sale_orders:
        lines = api.do("sale.order.line", "search_read", [('order_id', '=', sale_order['id'])],
                       ['name', 'price_unit', 'price_subtotal', 'product_uom_qty'])
        res.append({"amount_total": sale_order['amount_total'],
                    "create_date": sale_order['create_date'],
                    "id": sale_order['id'],
                    "name": sale_order['name'],
                    "state": sale_order['state'],
                    "agent_id": sale_order['partner_id'][0],
                    "agent_name": sale_order['partner_id'][1],
                    "sale_order_lines": lines,
                    })

    return res


@app.route('/order_details/<int:order_id>', methods=['GET'])
@basic_auth.required
def get_order_details(order_id):
    '''
    Get order details for a particular agent
    :return:
    '''
    try:
        res = api.do('sale.order.line', 'search_read', [('order_id', '=', order_id)],
                     ['name', 'price_unit', 'product_uom_qty'])

        if res:
            response = format_output(0, res, None)
        else:
            response = format_output(10, None, "No Sales Orders for this period")
    except Exception as error:
        print(traceback.format_exc(error))
        response = format_output(10, None, "Something went wrong try again. If issue persists contact administrator")
    return jsonify(response)


@app.route('/get_stock_available/<int:product_id>', methods=['GET'])
@basic_auth.required
def get_stock_available(product_id):
    '''
    Get order details for a particular agent
    :return:
    '''
    try:
        res = api.do_kw("product.product", 'search_read', [[('id', '=', product_id)]],
                        {'fields': ['qty_available']})
        if res:
            response = format_output(0, res[0], None)
        else:
            response = format_output(10, None, "No Pricelists found")
    except Exception as error:
        print(traceback.format_exc(error))
        response = format_output(10, None, "Something went wrong try again. If issue persists contact administrator")
    return jsonify(response)


@app.route('/get_pricelist/<int:product_id>/<int:erp_id>', methods=['GET'])
@basic_auth.required
def get_pricelist(product_id, erp_id):
    '''
    Get order details for a particular agent
    :return:
    '''
    try:
        product = api.do_kw('product.product', 'search_read',
                            [[('id', '=', product_id)]],
                            {'fields': ['product_tmpl_id']})[0]

        agent_ids = api.do_kw('res.partner', 'search_read',
                              [[('sale_associate_id', '=', erp_id)]],
                              {'fields': ['property_product_pricelist']})

        pricelist = _get_unique_pricelist(agent_ids)

        res = api.do_kw('product.pricelist.item', 'search_read',
                        [['|', ('product_tmpl_id', '=', product.get('product_tmpl_id')[0]),
                          ('product_id', '=', product.get('id')), ('pricelist_id', 'in', pricelist)]],
                          {'fields':['pricelist_id', 'price_surcharge', 'product_tmpl_id', 'product_id']})
        if res:
            response = format_output(0, _format_pricelist(res), None)
        else:
            response = format_output(10, None, "No Pricelists found")
    except Exception as error:
        print(traceback.format_exc(error))
        response = format_output(10, None, "Something went wrong try again. If issue persists contact administrator")
    return jsonify(response)


@app.route('/get_pricelist/<int:product_id>', methods=['GET'])
@basic_auth.required
def get_pricelist_old(product_id):
    '''
    Get order details for a particular agent
    :return:
    '''
    try:
        product = api.do_kw('product.product', 'search_read',
                            [[('id', '=', product_id)]],
                            {'fields': ['product_tmpl_id']})[0]
        res = api.do_kw('product.pricelist.item', 'search_read',
                        [['|', ('product_tmpl_id', '=', product.get('product_tmpl_id')[0]),
                          ('product_id', '=', product.get('id'))]],
                        {'fields': ['pricelist_id', 'price_surcharge', 'product_tmpl_id', 'product_id']})
        if res:
            response = format_output(0, _format_pricelist(res), None)
        else:
            response = format_output(10, None, "No Pricelists found")
    except Exception as error:
        print(traceback.format_exc(error))
        response = format_output(10, None, "Something went wrong try again. If issue persists contact administrator")
    return jsonify(response)


def _get_unique_pricelist(agents):
    response = []
    for agent in agents:
        pricelist_id = agent.get('property_product_pricelist')[0]
        if not pricelist_id in response:
            response.append(pricelist_id)

    return response


def _format_pricelist(pricelists):
    res = []
    for pricelist in pricelists:
        res.append({
            'price_surcharge': pricelist.get('price_surcharge', None),
            'pricelist_id': pricelist.get('pricelist_id', None)[0],
            'pricelist_name': pricelist.get('pricelist_id', None)[1],
            'product_id': pricelist.get('product_id', None)[0] if pricelist.get('product_tmpl_id') == False else
            pricelist.get('product_tmpl_id', None)[0],
            'product_name': pricelist.get('product_id', None)[1] if pricelist.get('product_tmpl_id') == False else
            pricelist.get('product_tmpl_id', None)[1],
        })

    return res


@app.route('/process_order', methods=['POST'])
@basic_auth.required
def process_order():
    '''
    Process orders online
    :return:
    '''
    try:
        erpId = request.form.get('erp_id', None)
        phone = api.do_kw('res.partner', 'search_read', [[('id', '=', erpId)]], {'fields': ['phone', 'mobile']})
        phone_number = phone[0].get('phone', None)
        # phone_number = str.replace(phone_number, '+254', '0')
        text = request.form.get('text', None)

        sms = {}
        sms['from'] = phone_number
        sms['to'] = '40707'
        sms['text'] = text
        content = json.dumps(sms)
        print(content)
        DataProvisionClient('inbound_queue_consumer', content)
        print(request.remote_addr)
        response = format_output(0, True)
    except Exception as error:
        print(traceback.format_exc(error))
        response = format_output(10, False, "Something went wrong try again. If issue persists contact administrator")
    return jsonify(response)


@app.route('/cancel_order', methods=['POST'])
@basic_auth.required
def cancel_order():
    '''
    Cancel orders online
    :return:
    '''
    try:
        order_number = request.form.get('so_number', None)
        erp_id = request.form.get('erp_id', None)
        res = api.do_kw("res.partner", "search_read", [[
            ('id', '=', erp_id), ('partner_type', '=', 'agent'), ('can_purchase', '=', True),
            ('active_agent', '=', True)]], {'fields': ['phone', 'mobile']})[0]
        res = api.do_kw("sale.order", "cancel_order_sms", [order_number, res.get('phone')])
        if res:
            response = format_output(0, res, None)
        else:
            response = format_output(10, None, "No Pricelists found")
    except Exception as error:
        print(traceback.format_exc(error))
        response = format_output(10, None, "Something went wrong try again. If issue persists contact administrator")
    return jsonify(response)


def format_output(status, data, message=None):
    return {'status': status, 'data': data, 'message': message}
