# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools
from datetime import datetime


class ShiftMaster(models.Model):

    _name = "hm.shift.master"
    _description = "Shift Master"

    name = fields.Many2one('res.partner', string="Name", required=True)
    from_date_time = fields.Datetime(string="From Time", required=True)
    to_date_time = fields.Datetime(string="To Time", required=True)


class PosSession(models.Model):
    _inherit = 'pos.session'

    shift_master_id = fields.Many2one('hm.shift.master', string="Shift")
    hand_over_to = fields.Many2one('res.users', string="Hand over to")
    rooms_available = fields.Char(string="Available Rooms",
                                  compute='_compute_all_room_count',
                                  )
    rooms_occupied = fields.Char(string="Occupied Rooms",
                                 compute='_compute_all_room_count',
                                 )
    rooms_reserved = fields.Char(string="Reserved Rooms",
                                 compute='_compute_all_room_count',
                                 )
    rooms_blocked = fields.Char(string="Blocked/Maintenance Rooms",
                                compute='_compute_all_room_count',
                                )
    room_details_of_order = fields.One2many('hm.service.details',
                                            'pos_session_id',
                                            string="Rooms")
    service_details_of_order = fields.One2many('pos.order.line',
                                               'pos_session_id',
                                               string="Service",
                                               domain=[('product_id.categ_id.is_service',
                                                        '=',
                                                        True)])

    @api.one
    def _compute_all_room_count(self):
        """ Display rooms count in session"""
        product_ids = self.env['product.template'].sudo().search([
                                        ('categ_id.is_room', '=', True),
                                        ('available_in_pos', '=', True),
                                        ])
        available_rooms_count = 0
        reserved_rooms_count = 0
        occupied_rooms_count = 0
        blocked_rooms_count = 0
        for product_id in product_ids:
            date = datetime.today().strftime('%Y-%m-%d')
            sql_query = "select id from product_history ph where \
                            ph.product_tmpl_id="+str(product_id.id)+" and\
                            to_date('"+str(date)+"','YYYY-MM-DD') \
                            BETWEEN DATE(ph.date) AND DATE(ph.out_date - INTERVAL '1 DAY')\
                            order by id desc LIMIT 1"
            self.env.cr.execute(sql_query)
            prod_history = self.env.cr.fetchall()
            if prod_history:
                history = self.env['product.history'].sudo().search([
                                    ('id', 'in', prod_history)])
                if ((history.state == 'checkout') or
                    (history.state == 'cancel') or
                    (history.state == 'draft')):
                    available_rooms_count += 1
                if ((history.state == 'checkin') or
                    (history.state == 'shift') or
                    (history.state == 'extend')):
                    occupied_rooms_count += 1
                if (history.state == 'reserved'):
                    reserved_rooms_count += 1
                if (history.state == 'block'):
                    blocked_rooms_count += 1
            else:
                available_rooms_count += 1
        self.rooms_available = available_rooms_count
        self.rooms_reserved = reserved_rooms_count
        self.rooms_occupied = occupied_rooms_count
        self.rooms_blocked = blocked_rooms_count

    @api.multi
    def save_hand_order(self, hand_over_id):
        if hand_over_id:
            self.write({'hand_over_to': hand_over_id})


class ServiceDetails(models.Model):
    """Service Details
    """
    _name = 'hm.service.details'
    _auto = False

    id = fields.Integer(string="Pos order line Id", readonly=True)
    pos_session_id = fields.Many2one('pos.session', string="Session Id")
    product_id = fields.Many2one(
        'product.product',
        string="Room No.",
        readonly=True
    )
    partner_id = fields.Many2one(
        'res.partner',
        string="Guest",
        readonly=True
    )
    amount = fields.Float(string="Amount", readonly=True)
    payment_mode = fields.Many2one('account.journal',
                                   string="Payment Mode",
                                   readonly=True)
    checkin_date = fields.Datetime(string="Check in", readonly=True)
    checkout_date = fields.Datetime(string="Check out", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self._cr, 'hm_service_details')
        self._cr.execute("""CREATE OR REPLACE VIEW hm_service_details AS (
        SELECT
            line.id AS id,
            porder.session_id AS pos_session_id,
            line.product_id AS product_id,
            porder.amount_total AS amount,
            porder.partner_id AS partner_id,
            line.checkin_date AS checkin_date,
            line.checkout_date AS checkout_date,
            stmt_line.journal_id AS payment_mode
            FROM pos_order porder
            INNER JOIN pos_order_line line ON porder.id = line.order_id
            INNER JOIN account_bank_statement_line stmt_line ON porder.id = stmt_line.pos_statement_id
            INNER JOIN product_product product ON product.id = line.product_id
            INNER JOIN product_template prod_temp ON prod_temp.id = product.product_tmpl_id 
            INNER JOIN product_category prod_categ ON prod_categ.id = prod_temp.categ_id
            WHERE prod_categ.is_room = true
            ); """)


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    pos_session_id = fields.Many2one('pos.session', string="Session Id")

    @api.model
    def create(self, values):
        session_id = self.order_id.browse(values['order_id']).session_id.id
        values['pos_session_id'] = session_id
        return super(PosOrderLine, self).create(values)


class RoomDetails(models.Model):
    """Service Details
    """
    _name = 'hm.room.details'
    _auto = False

    id = fields.Integer(string="Pos order line Id", readonly=True)
    pos_session_id = fields.Many2one('pos.session', string="Session Id")
    product_id = fields.Many2one(
        'product.product',
        string="Room No.",
        readonly=True
    )
    partner_id = fields.Many2one(
        'res.partner',
        string="Guest",
        readonly=True
    )
    amount = fields.Float(string="Amount", readonly=True)
    payment_mode = fields.Many2one('account.journal',
                                   string="Payment Mode",
                                   readonly=True)
    checkin_date = fields.Datetime(string="Check in", readonly=True)
    checkout_date = fields.Datetime(string="Check out", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self._cr, 'hm_room_details')
        self._cr.execute("""CREATE OR REPLACE VIEW hm_room_details AS (
        SELECT
            line.id AS id,
            porder.session_id AS pos_session_id,
            line.product_id AS product_id,
            porder.amount_total AS amount,
            porder.partner_id AS partner_id,
            line.checkin_date AS checkin_date,
            line.checkout_date AS checkout_date,
            stmt_line.journal_id AS payment_mode
            FROM pos_order porder
            INNER JOIN pos_order_line line ON porder.id = line.order_id
            INNER JOIN account_bank_statement_line stmt_line ON porder.id = stmt_line.pos_statement_id
            INNER JOIN product_product product ON product.id = line.product_id
            INNER JOIN product_template prod_temp ON prod_temp.id = product.product_tmpl_id 
            INNER JOIN product_category prod_categ ON prod_categ.id = prod_temp.categ_id
            WHERE prod_categ.is_room = true
            ); """)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    session_id = fields.Many2one('pos.session', string="POS Session")
    pos_order_id = fields.Many2one('pos.order', string="POS Order")


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    session_id = fields.Many2one('pos.session', string="POS Session")
    pos_order_id = fields.Many2one('pos.order', string="POS Order")