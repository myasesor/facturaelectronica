# -*- coding: utf-8 -*-
from openerp import api, fields, models, _, tools
from openerp.exceptions import UserError, ValidationError
from datetime import datetime, timedelta, date
from dateutil.relativedelta import *
from pytz import timezone

import logging

_logger = logging.getLogger(__name__)

try:
    from lxml import etree
except:
    print("Cannot import  etree")

from openerp.tools.translate import _

try:
    import pyqrcode
except ImportError:
    _logger.warning('Cannot import pyqrcode library ***********************')

try:
    import png
except ImportError:
    _logger.warning('Cannot import png library ***********************')

try:
    import hashlib
except ImportError:
    _logger.warning('Cannot import hashlib library ***********************')

try:
    import base64
except ImportError:
    _logger.warning('Cannot import base64 library ***********************')

try:
    import textwrap
except:
    _logger.warning("no se ha cargado textwrap ***********************")

try:
    import gzip
except:
    _logger.warning("no se ha cargado gzip ***********************")

import zipfile

try:
    import zlib
    compression = zipfile.ZIP_DEFLATED
except:
    compression = zipfile.ZIP_STORED

try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    import OpenSSL
    from OpenSSL import crypto
    type_ = crypto.FILETYPE_PEM
except:
    _logger.warning('Cannot import OpenSSL library')

from random import randint

try:
    import requests 
except:    
    _logger.warning("no se ha cargado requests")
 
try:
    import xmltodict
except ImportError:
    _logger.warning('Cannot import xmltodict library')

try:
    import uuid
except ImportError:
    _logger.warning('Cannot import uuid library')
            
server_url = {
    'HABILITACION':'https://facturaelectronica.dian.gov.co/habilitacion/B2BIntegrationEngine/FacturaElectronica/facturaElectronica.wsdl',
    'PRODUCCION':'https://facturaelectronica.dian.gov.co/operacion/B2BIntegrationEngine/FacturaElectronica/facturaElectronica.wsdl',
    'HABILITACION_CONSULTA':'https://facturaelectronica.dian.gov.co/habilitacion/B2BIntegrationEngine/FacturaElectronica/consultaDocumentos.wsdl',
    'PRODUCCION_CONSULTA':'https://facturaelectronica.dian.gov.co/operacion/B2BIntegrationEngine/FacturaElectronica/consultaDocumentos.wsdl',
    'PRODUCCION_VP':'https://colombia-dian-webservices-input-sbx.azurewebsites.net/WcfDianCustomerServices.svc?wsdl',
    'HABILITACION_VP':'https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc?wsdl'
}

tipo_ambiente = {
    'PRODUCCION':'1',
    'PRUEBA':'2'
}

tributes = {
   '01':'IVA', '02':'IC', '03':'ICA', '04':'INC', '05':'ReteIVA', '06':'ReteFuente', '07':'ReteICA', 
   '08':'ReteCREE', '20':'FtoHorticultura', '21':'Timbre', '22':'Bolsas', '23':'INCarbono', '24':'INCombustibles',
   '25':'Sobretasa Combustibles', '26':'Sordicom', 'ZZ':'Nombre de la figura tributaria'
}

import os

class DianDocument(models.Model):
    _name = 'dian.document'
    _rec_name = 'dian_code'

    document_id = fields.Many2one('account.invoice', string="N??mero de documento", readonly=True, required=True)
    state = fields.Selection([('por_notificar', 'Por notificar'), 
                            ('error', 'Error'), 
                            ('por_validar', 'Por validar'), 
                            ('exitoso', 'Exitoso'), 
                            ('rechazado', 'Rechazado')],
                            string="Estatus",
                            readonly=True,
                            default='por_notificar',
                            required=True)
    date_document_dian = fields.Char(string="Fecha envio al DIAN", readonly=True)
    shipping_response = fields.Selection([('100','100 Error al procesar la solicitud WS entrante'),
                                        ('101','101 El formato de los datos del ejemplar recibido no es correcto: Las entradas de directorio no est??n permitidos'),
                                        ('102','102 El formato de los datos del ejemplar recibido no es correcto: Tama??o de archivo comprimido zip es 0 o desconocido'), 
                                        ('103','103 Tama??o de archivo comprimido zip es 0 o desconocido'),
                                        ('104','104 S??lo un archivo es permitido por archivo Zip'), 
                                        ('200','200 Ejemplar recibido exitosamente pasar?? a verificaci??n'),
                                        ('300','300 Archivo no soportado: Solo reconoce los tipos Invoice, DebitNote o CreditNote'),
                                        ('310','310 El ejemplar contiene errores de validaci??n semantica'), 
                                        ('320','320 Par??metros de solicitud de servicio web, no coincide contra el archivo'),
                                        ('500','500 Error interno del servicio intentar nuevamente')],
                            string="Respuesta de env??o",
                            readonly=True)
    transaction_code = fields.Integer(string='C??digo de la Transacci??n de validaci??n', readonly=True)
    transaction_description = fields.Char(string='Descripci??n de la transacci??n de validaci??n', readonly=True)
    response_document_dian = fields.Selection([('7200001','7200001 Recibida'),
                                            ('7200002','7200002 Exitosa'),
                                            ('7200003','7200003 En proceso de validaci??n'),
                                            ('7200004','7200004 Fallida (Documento no cumple 1 o m??s validaciones de DIAN)'),
                                            ('7200005','7200005 Error (El xml no es v??lido)')],
                            string="Respuesta de consulta",
                            readonly=True)
    dian_code = fields.Char(string='C??digo DIAN', readonly=True)
    xml_document = fields.Text(string='Contenido XML', readonly=True)
    xml_file_name = fields.Char(string='Nombre archivo xml', readonly=True)
    zip_file_name = fields.Char(string='Nombre archivo zip', readonly=True)
    date_request_dian = fields.Datetime(string="Fecha consulta DIAN", readonly=True)
    cufe = fields.Char(string='CUFE', readonly=True)
    QR_code = fields.Binary(string='C??digo QR', readonly=True)
    date_email_send = fields.Datetime(string="Fecha env??o email", readonly=True)
    date_email_acknowledgment = fields.Datetime(string="Fecha acuse email", readonly=True)
    response_message_dian = fields.Text(string="Respuesta DIAN", readonly=True)
    last_shipping = fields.Boolean(string="Ultimo env??o", default=True)
    customer_name = fields.Char(string="Cliente", readonly=True, related='document_id.partner_id.name')
    date_document = fields.Date(string="Fecha documento", readonly=True, related='document_id.date_invoice')
    customer_email = fields.Char(string="Email cliente", readonly=True, related='document_id.partner_id.email')
    document_type = fields.Selection([('f','Factura'), ('c','Nota/Credito'), ('d','Nota/Debito')], string="Tipo de documento", readonly=True)
    resend = fields.Boolean(string="Autorizar reenvio?", default=False)
    email_response = fields.Selection([('accepted','ACEPTADA'),('rejected','RECHAZADA'),('pending','PENDIENTE')], string='Decisi??n del cliente', required=True, default='pending', readonly=True)
    email_reject_reason = fields.Char(string='Motivo del rechazo', readonly=True)
    ZipKey = fields.Char(string='Identificador del docuemnto enviado', readonly=True)


    @api.multi
    def generate_new_dian_document(self):
        self.ensure_one()
        self.resend = False
        self.last_shipping = False
        vals = {'document_id' : self.document_id.id, 'document_type' : self.document_type}
        new_dian_document = self.create(vals)
        return new_dian_document


    @api.model
    def _get_resolution_dian(self, data_header_doc):
        # Falta preguntar si con un mismo n??mero de resoluci??n DIAN se puede generar consecutivos de facturas
        # notas de d??bto y cr??dito. 
        # dian_sequence = int(self.env.user.partner_id.company_id.in_use_dian_sequence)
        # rec_dian_sequence = self.env['ir.sequence'].search([('id', '=', dian_sequence),('use_dian_control', '=', True),('active', '=', True)])
        # if not rec_dian_sequence:
        #     raise ValidationError('No se pueden generar documentos para la DIAN porque no hay secuenciador DIAN activo.')
        # rec_active_resolution = self.env['ir.sequence.dian_resolution'].search([('sequence_id', '=', rec_dian_sequence.id),('active_resolution', '=', True)])
        rec_active_resolution = self.env['ir.sequence.dian_resolution'].search([('resolution_number', '=', data_header_doc.resolution_number)])
        dict_resolution_dian = {}
        if rec_active_resolution:
            rec_dian_sequence = self.env['ir.sequence'].search([('id', '=', rec_active_resolution.sequence_id.id)])
            # if not rec_active_resolution:
            #     raise ValidationError('No se puede generar documento para la DIAN porque no hay rango de resolucion DIAN activo.')
            dict_resolution_dian['Prefix'] = rec_dian_sequence.prefix                               # Prefijo de n??mero de factura
            dict_resolution_dian['InvoiceAuthorization'] = rec_active_resolution.resolution_number  # N??mero de resoluci??n
            dict_resolution_dian['StartDate'] = rec_active_resolution.date_from                     # Fecha desde resoluci??n
            dict_resolution_dian['EndDate'] = rec_active_resolution.date_to                         # Fecha hasta resoluci??n
            dict_resolution_dian['From'] = rec_active_resolution.number_from                        # Desde la secuencia
            dict_resolution_dian['To'] = rec_active_resolution.number_to                            # Hasta la secuencia
            dict_resolution_dian['TechnicalKey'] = rec_active_resolution.technical_key              # Clave t??cnica de la resoluci??n de rango
            dict_resolution_dian['InvoiceID'] = data_header_doc.number                              # Codigo del documento
            
        else:
            raise ValidationError("El n??mero de resoluci??n DIAN asociada a la factura no existe")
        return dict_resolution_dian


    @api.model
    def request_validating_dian(self, document_id):
        dian_document = self.env['dian.document'].search([('id', '=', document_id)])
        data_header_doc = self.env['account.invoice'].search([('id', '=', dian_document.document_id.id)])
        dian_constants = self._get_dian_constants(data_header_doc)
        trackId = dian_document.ZipKey
        identifier = uuid.uuid4()
        identifierTo = uuid.uuid4()
        identifierSecurityToken = uuid.uuid4()
        timestamp = self._generate_datetime_timestamp()
        Created = timestamp['Created']
        Expires = timestamp['Expires']

        template_GetStatus_xml = self._template_GetStatus_xml()
        data_xml_send = self._generate_GetStatus_send_xml(template_GetStatus_xml, identifier, Created, Expires, 
            dian_constants['Certificate'], identifierSecurityToken, identifierTo, trackId)
        
        parser = etree.XMLParser(remove_blank_text=True)
        data_xml_send = etree.tostring(etree.XML(data_xml_send, parser=parser))
        #   Generar DigestValue Elemento to y lo reemplaza en el xml
        ElementTO = etree.fromstring(data_xml_send)
        ElementTO = etree.tostring(ElementTO[0])
        ElementTO = etree.fromstring(ElementTO)
        ElementTO = etree.tostring(ElementTO[2])
        DigestValueTO = self._generate_digestvalue_to(ElementTO)
        data_xml_send = data_xml_send.replace('<ds:DigestValue/>','<ds:DigestValue>%s</ds:DigestValue>' % DigestValueTO)
        #   Generar firma para el header de env??o con el Signedinfo
        Signedinfo = etree.fromstring(data_xml_send)
        Signedinfo = etree.tostring(Signedinfo[0])
        Signedinfo = etree.fromstring(Signedinfo)
        Signedinfo = etree.tostring(Signedinfo[0])
        Signedinfo = etree.fromstring(Signedinfo)
        Signedinfo = etree.tostring(Signedinfo[2])
        Signedinfo = etree.fromstring(Signedinfo)
        Signedinfo = etree.tostring(Signedinfo[0])
        Signedinfo = Signedinfo.replace('<ds:SignedInfo xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd" xmlns:wsa="http://www.w3.org/2005/08/addressing" xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wcf="http://wcf.dian.colombia">',
                                        '<ds:SignedInfo xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wcf="http://wcf.dian.colombia" xmlns:wsa="http://www.w3.org/2005/08/addressing">')
        SignatureValue = self._generate_SignatureValue_GetStatus(dian_constants['document_repository'], dian_constants['CertificateKey'], Signedinfo)
        data_xml_send = data_xml_send.replace('<ds:SignatureValue/>','<ds:SignatureValue>%s</ds:SignatureValue>' % SignatureValue)
        #   Contruye XML de env??o de petici??n
        headers = {'content-type': 'application/soap+xml'}
        try:
             response = requests.post(server_url['HABILITACION_VP'],data=data_xml_send,headers=headers)
        except:
             raise ValidationError('No existe comunicaci??n con la DIAN para el servicio de recepci??n de Facturas Electr??nicas')
        #   Respuesta de petici??n
        if response.status_code != 200: # Respuesta de env??o no exitosa
            if response.status_code == 500:
                raise ValidationError('Error 500 = Error de servidor interno')
            if response.status_code == 503:
                raise ValidationError('Error 503 = Servicio no disponible')

        response_dict = xmltodict.parse(response.content)
        # print('------------------------------------------------------------------------------------')
        # print('response.content ', response.content)
        # print('response_dict ', response_dict)
        # print('------------------------------------------------------------------------------------')
        # Faltan mensajes m??s detallados
        if response_dict['s:Envelope']['s:Body']['GetStatusZipResponse']['GetStatusZipResult']['b:DianResponse']['b:StatusCode'] == '00':
            data_header_doc.write({'diancode_id' : dian_document.id})
            dian_document.response_message_dian += '- Respuesta consulta estado de la factura: Procesado correctamente \n'
            plantilla_correo = self.env.ref('l10n_co_e-invoice.email_template_edi_invoice_dian', False)
            plantilla_correo.send_mail(dian_document.document_id.id, force_send = True)
            dian_document.date_email_send = fields.Datetime.now()
            dian_document.write({'state' : 'exitoso', 'resend' : False})
        else:
            data_header_doc.write({'diancode_id' : dian_document.id})
            if response_dict['s:Envelope']['s:Body']['GetStatusZipResponse']['GetStatusZipResult']['b:DianResponse']['b:StatusCode'] == '90':
                dian_document.response_message_dian += '- Respuesta consulta estado de la factura: TrackId no encontrado'
                dian_document.write({'state' : 'por_validar', 'resend' : False})
            elif response_dict['s:Envelope']['s:Body']['GetStatusZipResponse']['GetStatusZipResult']['b:DianResponse']['b:StatusCode'] == '99':
                dian_document.response_message_dian += '- Respuesta consulta estado de la factura: Validaciones contiene errores en campos mandatorios'
                dian_document.write({'state' : 'rechazado', 'resend' : True})
            elif response_dict['s:Envelope']['s:Body']['GetStatusZipResponse']['GetStatusZipResult']['b:DianResponse']['b:StatusCode'] == '66':
                dian_document.response_message_dian += '- Respuesta consulta estadola de la factura: NSU no encontrado'
                dian_document.write({'state' : 'por_validar', 'resend' : False})
        return True


    @api.model
    def send_pending_dian(self, document_id, document_type):
        data_lines_xml = ''
        data_credit_lines_xml = ''
        data_xml_signature = ''
        template_basic_data_fe_xml = self._template_basic_data_fe_xml()
        template_basic_data_nc_xml = self._template_basic_data_nc_xml()
        template_tax_data_xml = self._template_tax_data_xml()
        template_line_data_xml = self._template_line_data_xml()
        template_credit_line_data_xml = self._template_credit_line_data_xml()
        template_signature_data_xml = self._template_signature_data_xml()
        template_send_data_xml = self._template_send_data_xml()
        
        # Se obtienen los documento a enviar
        by_validate_invoices = self.env['dian.document'].search([('id', '=', document_id),('document_type', '=', document_type)])
        by_validate_credit_notes = self.env['dian.document'].search([('id', '=', document_id),('document_type', '=', document_type)])
        cn_with_validated_invoices_ids = []
        for by_validate_cn in by_validate_credit_notes:
            invoice_validated = self.env['account.invoice'].search([('move_name', '=', by_validate_cn.document_id.origin),('type', '=', 'out_invoice'),('state_dian_document', '=', 'exitoso')])
            if invoice_validated:
                cn_with_validated_invoices_ids.append(by_validate_cn.id)
        by_validate_credit_notes_autorized = self.env['dian.document'].browse(cn_with_validated_invoices_ids)
        docs_send_dian = by_validate_invoices + by_validate_credit_notes_autorized
        for doc_send_dian in docs_send_dian:
            data_header_doc = self.env['account.invoice'].search([('id', '=', doc_send_dian.document_id.id)])
            dian_constants = self._get_dian_constants(data_header_doc)
            # Se obtienen constantes del documento
            data_constants_document = self._generate_data_constants_document(data_header_doc, dian_constants)            
            # Construye el documento XML para la factura sin firma
            if data_constants_document['InvoiceTypeCode'] == '01':
                # Genera l??neas de detalle de los impuestos
                data_taxs = self._get_taxs_data(data_header_doc.id)
                data_taxs_xml = self._generate_taxs_data_xml(template_tax_data_xml, data_taxs)
                # Genera l??neas de detalle de las factura
                data_lines_xml = self._generate_lines_data_xml(template_line_data_xml, data_header_doc.id)
                # Generar CUFE
                CUFE = self._generate_cufe(data_header_doc.id, data_constants_document['InvoiceID'], data_constants_document['IssueDateCufe'], 
                                        data_constants_document['IssueTime'], data_constants_document['LineExtensionAmount'],
                                        dian_constants['SupplierID'], data_constants_document['CustomerSchemeID'],
                                        data_constants_document['CustomerID'], data_constants_document['TechnicalKey'], data_constants_document['PayableAmount'], 
                                        data_taxs, tipo_ambiente['PRUEBA'])
                doc_send_dian.cufe = CUFE
                # Genera documento xml de la factura
                template_basic_data_fe_xml = '<?xml version="1.0" encoding="UTF-8"?>' + template_basic_data_fe_xml
                parser = etree.XMLParser(remove_blank_text=True)
                template_basic_data_fe_xml = etree.tostring(etree.XML(template_basic_data_fe_xml, parser=parser))
                data_xml_document = self._generate_data_fe_document_xml(template_basic_data_fe_xml, dian_constants, data_constants_document, data_taxs_xml, data_lines_xml, CUFE, data_xml_signature)
                # Elimina espacios del documento xml la factura
                parser = etree.XMLParser(remove_blank_text=True)
                data_xml_document = etree.tostring(etree.XML(data_xml_document, parser=parser))
            # Construye el documento XML para la nota de cr??dito sin firma
            if data_constants_document['InvoiceTypeCode'] == '91':
                data_taxs = self._get_taxs_data(data_header_doc.id)
                data_taxs_xml = self._generate_taxs_data_xml(template_tax_data_xml, data_taxs)
                # Detalle l??neas de nota de cr??dito                
                data_credit_lines_xml = self._generate_credit_lines_data_xml(template_credit_line_data_xml, data_header_doc.id, data_constants_document)
                # Generar CUFE OJO CUDE
                CUFE = self._generate_cufe(data_header_doc.id, data_constants_document['InvoiceID'], data_constants_document['IssueDateCufe'], 
                        data_constants_document['IssueTime'], data_constants_document['LineExtensionAmount'],
                        dian_constants['SupplierID'], data_constants_document['CustomerSchemeID'],
                        data_constants_document['CustomerID'], data_constants_document['TechnicalKey'], data_constants_document['PayableAmount'], 
                        data_taxs, tipo_ambiente['PRUEBA'])
                doc_send_dian.cufe = CUFE
                # Genera documento xml de la nota de credito
                data_xml_document = self._generate_data_nc_document_xml(template_basic_data_nc_xml, dian_constants, data_constants_document, data_credit_lines_xml, CUFE, data_taxs_xml)
                # Elimina espacios del documento xml
                parser = etree.XMLParser(remove_blank_text=True)
                data_xml_document = etree.tostring(etree.XML(data_xml_document, parser=parser))
            # Genera la firma en el documento xml
            data_xml_document = data_xml_document.replace("<ext:ExtensionContent/>","<ext:ExtensionContent></ext:ExtensionContent>")
            data_xml_signature = self._generate_signature(data_xml_document, template_signature_data_xml, dian_constants, data_constants_document)
            data_xml_signature = etree.tostring(etree.XML(data_xml_signature, parser=parser))
            # Construye el documento XML con firma
            data_xml_document = data_xml_document.replace("<ext:ExtensionContent></ext:ExtensionContent>","<ext:ExtensionContent>%s</ext:ExtensionContent>" % data_xml_signature)
            data_xml_document = '<?xml version="1.0" encoding="UTF-8"?>' + data_xml_document
            # Generar codigo DIAN       
            doc_send_dian.dian_code = data_constants_document['InvoiceID']
            # Generar nombre del archvio xml
            doc_send_dian.xml_file_name = data_constants_document['FileNameXML']
            # Almacenar archivo xml
            doc_send_dian.xml_document = data_xml_document
            # Generar nombre archvio ZIP
            doc_send_dian.zip_file_name = data_constants_document['FileNameZIP']
            # Comprimir documento electr??nico         
            Document = self._generate_zip_content(data_constants_document['FileNameXML'], data_constants_document['FileNameZIP'], data_xml_document, dian_constants['document_repository'])
            fileName = data_constants_document['FileNameZIP'][:-4]
            # Fecha y hora de la petici??n y expiraci??n del env??o del documento
            timestamp = self._generate_datetime_timestamp()
            Created = timestamp['Created']
            Expires = timestamp['Expires']
            doc_send_dian.date_document_dian = data_constants_document['IssueDateSend']
            # Id de pruebas ante la DIAN (Ojo Quitar cuando se terminen las pruebas)
            testSetId = '6f9f8512-fc07-4b19-b3b5-0ac7f966d0fc'
            # Preparaci??n del env??o de la factura a trav??s del m??todo SendTestSetAsync
            template_SendTestSetAsyncsend_xml = self._template_SendTestSetAsyncsend_xml()
            identifierSecurityToken = uuid.uuid4()
            identifierTo = uuid.uuid4()
            #   Generar xml de env??o del m??todo SendTestSetAsync
            data_xml_send = self._generate_SendTestSetAsync_send_xml(template_SendTestSetAsyncsend_xml, fileName, 
                            Document, Created, testSetId, data_constants_document['identifier'], Expires, 
                            dian_constants['Certificate'], identifierSecurityToken, identifierTo)
            parser = etree.XMLParser(remove_blank_text=True)
            data_xml_send = etree.tostring(etree.XML(data_xml_send, parser=parser))
            #   Generar DigestValue Elemento to y lo reemplaza en el xml
            ElementTO = etree.fromstring(data_xml_send)
            ElementTO = etree.tostring(ElementTO[0])
            ElementTO = etree.fromstring(ElementTO)
            ElementTO = etree.tostring(ElementTO[2])
            DigestValueTO = self._generate_digestvalue_to(ElementTO)
            data_xml_send = data_xml_send.replace('<ds:DigestValue/>','<ds:DigestValue>%s</ds:DigestValue>' % DigestValueTO)
            #   Generar firma para el header de env??o con el Signedinfo
            Signedinfo = etree.fromstring(data_xml_send)
            Signedinfo = etree.tostring(Signedinfo[0])
            Signedinfo = etree.fromstring(Signedinfo)
            Signedinfo = etree.tostring(Signedinfo[0])
            Signedinfo = etree.fromstring(Signedinfo)
            Signedinfo = etree.tostring(Signedinfo[2])
            Signedinfo = etree.fromstring(Signedinfo)
            Signedinfo = etree.tostring(Signedinfo[0])
            Signedinfo = Signedinfo.replace('<ds:SignedInfo xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd" xmlns:wsa="http://www.w3.org/2005/08/addressing" xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wcf="http://wcf.dian.colombia">',
                                            '<ds:SignedInfo xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wcf="http://wcf.dian.colombia" xmlns:wsa="http://www.w3.org/2005/08/addressing">')
            SignatureValue = self._generate_SignatureValue_GetStatus(dian_constants['document_repository'], dian_constants['CertificateKey'], Signedinfo)
            data_xml_send = data_xml_send.replace('<ds:SignatureValue/>','<ds:SignatureValue>%s</ds:SignatureValue>' % SignatureValue)
            #   Contruye XML de env??o de petici??n
            headers = {'content-type': 'application/soap+xml'}
            try:
                 response = requests.post(server_url['HABILITACION_VP'],data=data_xml_send,headers=headers)
            except:
                 raise ValidationError('No existe comunicaci??n con la DIAN para el servicio de recepci??n de Facturas Electr??nicas')
            #   Respuesta de petici??n
            if response.status_code != 200: # Respuesta de env??o no exitosa
                if response.status_code == 500:
                    raise ValidationError('Error 500 = Error de servidor interno')
                if response.status_code == 503:
                    raise ValidationError('Error 503 = Servicio no disponible')
            #   Procesa respuesta DIAN 
            #response_dict = xmltodict.parse(respuesta)
            response_dict = xmltodict.parse(response.content)
            if response_dict['s:Envelope']['s:Body']['SendTestSetAsyncResponse']['SendTestSetAsyncResult']['b:ErrorMessageList']['@i:nil'] == 'true':
                doc_send_dian.response_message_dian = '- Respuesta env??o de factura: Documento enviado con ??xito. Falta validar su estado \n'
                doc_send_dian.ZipKey = response_dict['s:Envelope']['s:Body']['SendTestSetAsyncResponse']['SendTestSetAsyncResult']['b:ZipKey']
                doc_send_dian.state = 'por_validar'
            else:
                doc_send_dian.response_message_dian = '- Respuesta env??o de factura: Documento enviado con ??xito, pero la DIAN detect?? errores \n'
                doc_send_dian.ZipKey = response_dict['s:Envelope']['s:Body']['SendTestSetAsyncResponse']['SendTestSetAsyncResult']['b:ZipKey']
                doc_send_dian.state = 'por_notificar'

            # Generar c??digo QR
            doc_send_dian.QR_code = self._generate_barcode(dian_constants, data_constants_document, CUFE, data_taxs)

            print('------------------------------------------------------------------------------------')
            # print('response.status_code ', (response.status_code))
            print('response.content ', (response.content)) 
            # print('response.content ', (respuesta))
            # print('Parar ', parar)
            print('------------------------------------------------------------------------------------')
        return 

            # # GetNumberingRange 
            # # template_GetNumberingRange_xml = self._template_GetNumberingRange_xml()
            # # data_xml_send = self._generate_GetNumberingRange_send_xml(template_GetNumberingRange_xml, data_constants_document['identifier'], Created, Expires, 
            # #     dian_constants['Certificate'], dian_constants['ProviderID'], dian_constants['ProviderID'],
            # #     dian_constants['SoftwareID'], identifierSecurityToken, identifierTo)
            # # Env??o SOAP del m??todo SendTestSetAsync


    @api.multi
    def _generate_SignatureValue_GetStatus(self, document_repository, password, data_xml_SignedInfo_generate):
        data_xml_SignatureValue_c14n = etree.tostring(etree.fromstring(data_xml_SignedInfo_generate), method="c14n")
        archivo_key = document_repository+'/Certificado.p12'
        try:
            key = crypto.load_pkcs12(open(archivo_key, 'rb').read(), password)  
        except Exception as ex:
            raise UserError(tools.ustr(ex))
        try:
            signature = crypto.sign(key.get_privatekey(), data_xml_SignatureValue_c14n, 'sha256')               
        except Exception as ex:
            raise UserError(tools.ustr(ex))
        SignatureValue = base64.b64encode(signature)
        archivo_pem = document_repository+'/744524.pem'
        pem = crypto.load_certificate(crypto.FILETYPE_PEM, open(archivo_pem, 'rb').read())
        try:
            validacion = crypto.verify(pem, signature, data_xml_SignatureValue_c14n, 'sha256')
        except:
            raise ValidationError("Firma para el GestStatus no fu?? validada exitosamente")
        return SignatureValue


    @api.model
    def _generate_signature(self, data_xml_document, template_signature_data_xml, dian_constants, data_constants_document):
        data_xml_keyinfo_base = ''
        data_xml_politics = ''
        data_xml_SignedProperties_base = ''
        data_xml_SigningTime = ''
        data_xml_SignatureValue = ''
        # Generar clave de referencia 0 para la firma del documento (referencia ref0)
        # Actualizar datos de signature
        #    Generar certificado publico para la firma del documento en el elemento keyinfo 
        data_public_certificate_base = dian_constants['Certificate']
        #    Generar clave de politica de firma para la firma del documento (SigPolicyHash)
        data_xml_politics = self._generate_signature_politics(dian_constants['document_repository'])
        #    Obtener la hora de Colombia desde la hora del pc
        data_xml_SigningTime = self._generate_signature_signingtime()
        #    Generar clave de referencia 0 para la firma del documento (referencia ref0)
        #    1ra. Actualizaci??n de firma ref0 (leer todo el xml sin firma)
        data_xml_signature_ref_zero = self._generate_signature_ref0(data_xml_document, dian_constants['document_repository'], dian_constants['CertificateKey'])
        data_xml_signature = self._update_signature(template_signature_data_xml,  
                                data_xml_signature_ref_zero, data_public_certificate_base, 
                                data_xml_keyinfo_base, data_xml_politics, 
                                data_xml_SignedProperties_base, data_xml_SigningTime, 
                                dian_constants, data_xml_SignatureValue, data_constants_document)
        parser = etree.XMLParser(remove_blank_text=True)
        data_xml_signature = etree.tostring(etree.XML(data_xml_signature, parser=parser))
        #    Actualiza Keyinfo
        KeyInfo = etree.fromstring(data_xml_signature)
        KeyInfo = etree.tostring(KeyInfo[2])
        xmlns = 'xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" xmlns:sts="http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
        KeyInfo = KeyInfo.replace('xmlns:ds="http://www.w3.org/2000/09/xmldsig#"', '%s' % xmlns )
        data_xml_keyinfo_base = self._generate_signature_ref1(KeyInfo, dian_constants['document_repository'], dian_constants['CertificateKey'])        
        data_xml_signature = data_xml_signature.replace("<ds:DigestValue/>","<ds:DigestValue>%s</ds:DigestValue>" % data_xml_keyinfo_base, 1)
        #    Actualiza SignedProperties   
        SignedProperties = etree.fromstring(data_xml_signature)
        SignedProperties = etree.tostring(SignedProperties[3])
        SignedProperties = etree.fromstring(SignedProperties)
        SignedProperties = etree.tostring(SignedProperties[0])
        SignedProperties = etree.fromstring(SignedProperties)
        SignedProperties = etree.tostring(SignedProperties[0])
        xmlns = 'xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" xmlns:sts="http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures" xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
        SignedProperties = SignedProperties.replace('xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#" xmlns:ds="http://www.w3.org/2000/09/xmldsig#"', '%s' % xmlns )
        data_xml_SignedProperties_base = self._generate_signature_ref2(SignedProperties)
        data_xml_signature = data_xml_signature.replace("<ds:DigestValue/>","<ds:DigestValue>%s</ds:DigestValue>" % data_xml_SignedProperties_base, 1)
        #    Actualiza Signeinfo
        Signedinfo = etree.fromstring(data_xml_signature)
        Signedinfo = etree.tostring(Signedinfo[0])
        xmlns = 'xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" xmlns:sts="http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
        Signedinfo = Signedinfo.replace('xmlns:ds="http://www.w3.org/2000/09/xmldsig#"', '%s' % xmlns )
        data_xml_SignatureValue = self._generate_SignatureValue(dian_constants['document_repository'], dian_constants['CertificateKey'], Signedinfo)
        SignatureValue = etree.fromstring(data_xml_signature)
        SignatureValue = etree.tostring(SignatureValue[1])
        data_xml_signature = data_xml_signature.replace('-sigvalue"/>','-sigvalue">%s</ds:SignatureValue>' % data_xml_SignatureValue, 1)
        return data_xml_signature


    @api.model
    def _get_dian_constants(self, data_header_doc):
        user = self.env['res.users'].search([('id', '=', self.env.uid)])
        company = self.env['res.company'].search([('id', '=', user.company_id.id)])
        partner = company.partner_id 
        dian_constants = {}
        dian_constants['document_repository'] = company.document_repository                             # Ruta en donde se almacenaran los archivos que utiliza y genera la Facturaci??n Electr??nica
        dian_constants['Username'] = company.software_identification_code                               # Identificador del software en estado en pruebas o activo 
        dian_constants['Password'] = hashlib.new('sha256',company.password_environment).hexdigest()     # Es el resultado de aplicar la funci??n de resumen SHA-256 sobre la contrase??a del software en estado en pruebas o activo
        dian_constants['IdentificationCode'] = partner.country_id.code                                  # Identificador de pais
        dian_constants['ProviderID'] = partner.xidentification     if partner.xidentification else ''   # ID Proveedor de software o cliente si es software propio
        dian_constants['SoftwareID'] = company.software_identification_code                             # ID del software a utilizar
        dian_constants['SoftwareSecurityCode'] = self._generate_software_security_code(company.software_identification_code, 
                                                company.software_pin,data_header_doc.number)            # C??digo de seguridad del software: (hashlib.new('sha384', str(self.company_id.software_id) + str(self.company_id.software_pin)))
        dian_constants['SeedCode'] = company.seed_code
        dian_constants['UBLVersionID'] = 'UBL 2.1'                                                      # Versi??n base de UBL usada. Debe marcar UBL 2.0
        dian_constants['ProfileID'] = 'DIAN 2.1'                                                        # Versi??n del Formato: Indicar versi??n del documento. Debe usarse "DIAN 1.0"
        dian_constants['CustomizationID'] = company.operation_type  
        dian_constants['ProfileExecutionID'] = 2                                                        # 1 = produccci??n 2 = prueba
        dian_constants['SupplierAdditionalAccountID'] = '1' if partner.is_company else '2'              # Persona natural o jur??dica (persona natural, jur??dica, gran contribuyente, otros)
        dian_constants['SupplierID'] = partner.xidentification if partner.xidentification else ''       # Identificador fiscal: En Colombia, el NIT
        dian_constants['SupplierSchemeID'] = partner.doctype
        dian_constants['SupplierPartyName'] = self._replace_character_especial(partner.name)            # Nombre Comercial
        dian_constants['SupplierDepartment'] = partner.state_id.name                                    # Ciudad o departamento (No requerido)
        dian_constants['SupplierCityCode'] = partner.xcity.code                                         # Municipio tabla 6.4.3 res.country.state.city
        dian_constants['SupplierCityName'] = partner.xcity.name                                         # Municipio tabla 6.4.3 res.country.state.city
        dian_constants['SupplierCountrySubentity'] = partner.state_id.name                              # Ciudad o departamento tabla 6.4.2 res.country.state
        dian_constants['SupplierCountrySubentityCode'] = partner.state_id.code                          # Ciudad o departamento tabla 6.4.2 res.country.state
        dian_constants['SupplierCountryCode'] = partner.country_id.code                                 # Pa??s tabla 6.4.1 res.country
        dian_constants['SupplierCountryName'] = partner.country_id.name                                 # Pa??s tabla 6.4.1 res.country
        dian_constants['SupplierLine'] = partner.street                                                 # Calle
        dian_constants['SupplierRegistrationName'] = company.trade_name                                 # Raz??n Social: Obligatorio en caso de ser una persona jur??dica. Raz??n social de la empresa
        dian_constants['schemeID'] = partner.dv # Digito verificador del NIT
        dian_constants['SupplierElectronicMail'] = partner.email
        dian_constants['SupplierTaxLevelCode'] = partner.fiscal_responsability_id.code                  # tabla 6.2.4 R??gimes fiscal (listname) y 6.2.7 Responsabilidades fiscales
        dian_constants['Certificate'] = company.digital_certificate
        dian_constants['NitSinDV'] = partner.xidentification 
        dian_constants['CertificateKey'] = company.certificate_key 
        dian_constants['CertDigestDigestValue'] = self._generate_CertDigestDigestValue(company.digital_certificate, dian_constants['CertificateKey'], dian_constants['document_repository']) #Falta se presume que es el certificado publico convertido a sha256 base64
        dian_constants['IssuerName'] = company.issuer_name                                              # Nombre del proveedor del certificado
        dian_constants['SerialNumber'] = company.serial_number                                          # Serial del certificado
        dian_constants['TaxSchemeID'] = partner.tributes
        dian_constants['TaxSchemeName'] = tributes[partner.tributes]
        return dian_constants


    def _generate_data_constants_document(self, data_header_doc, dian_constants):
        NitSinDV = dian_constants['NitSinDV']
        data_constants_document = {}
        data_resolution  = self._get_resolution_dian(data_header_doc)
        # Generar nombre del archvio xml
        data_constants_document['FileNameXML'] = self._generate_xml_filename(data_resolution, NitSinDV, data_header_doc.type)
        data_constants_document['FileNameZIP'] = self._generate_zip_filename(data_resolution, NitSinDV, data_header_doc.type)
        data_constants_document['InvoiceAuthorization'] = data_resolution['InvoiceAuthorization']                           # N??mero de resoluci??n
        data_constants_document['StartDate'] = data_resolution['StartDate']                                                 # Fecha desde resoluci??n
        data_constants_document['EndDate'] = data_resolution['EndDate']                                                     # Fecha hasta resoluci??n
        data_constants_document['Prefix'] = data_resolution['Prefix']                                                       # Prefijo de n??mero de factura
        data_constants_document['From'] = data_resolution['From']                                                           # Desde la secuencia
        data_constants_document['To'] = data_resolution['To']                                                               # Hasta la secuencia
        data_constants_document['InvoiceID'] = data_resolution['InvoiceID']                                                 # N??mero de documento dian
        data_constants_document['Nonce'] = self._generate_nonce(data_resolution['InvoiceID'], dian_constants['SeedCode'])   # semilla para generar n??meros aleatorios
        data_constants_document['TechnicalKey'] = data_resolution['TechnicalKey']                                           # Clave t??cnica de la resoluci??n de rango
        data_constants_document['LineExtensionAmount'] = self._complements_second_decimal(data_header_doc.amount_untaxed)   # Total Importe bruto antes de impuestos: Total importe bruto, suma de los importes brutos de las l??neas de la factura.
        # Valor bruto m??s tributos
        data_constants_document['TotalTaxInclusiveAmount'] = self._complements_second_decimal(data_header_doc.amount_total) 
        data_constants_document['TaxExclusiveAmount'] = self._complements_second_decimal(data_header_doc.amount_untaxed)    # Total Base Imponible (Importe Bruto+Cargos-Descuentos): Base imponible para el c??lculo de los impuestos
        #data_constants_document['TaxExclusiveAmount'] = self._complements_second_decimal(data_header_doc.amount_tax)    # Total Base Imponible (Importe Bruto+Cargos-Descuentos): Base imponible para el c??lculo de los impuestos
        # Valor Bruto m??s tributos - Valor del Descuento Total + Valor del Cargo Total - Valor del Anticipo Total
        data_constants_document['PayableAmount'] = self._complements_second_decimal(data_header_doc.amount_total)           # Total de Factura: Total importe bruto + Total Impuestos-Total Impuesto Retenidos
        date_invoice_cufe = self._generate_datetime_IssueDate()
        data_constants_document['IssueDate'] = date_invoice_cufe['IssueDate']                                               # Fecha de emisi??n de la factura a efectos fiscales        
        data_constants_document['IssueDateSend'] = date_invoice_cufe['IssueDateSend']
        data_constants_document['IssueDateCufe'] = date_invoice_cufe['IssueDateCufe']
        data_constants_document['IssueTime'] = self._get_time_colombia()                                                             # Hora de emisi??n de la fcatura
        data_constants_document['InvoiceTypeCode'] = self._get_doctype(data_header_doc.type)                                # Tipo de Factura, c??digo: facturas de venta, y transcripciones; tipo = 1 para factura de venta 
        data_constants_document['LineCountNumeric'] = self._get_lines_invoice(data_header_doc.id)
        date_start_end_invoice = self._get_date_start_end_invoice(data_header_doc.date_invoice)
        data_constants_document['InvoicePeriodStartDate'] = date_start_end_invoice['InvoicePeriodStartDate']
        data_constants_document['InvoicePeriodEndDate'] = date_start_end_invoice['InvoicePeriodEndDate']
        data_constants_document['TaxSchemeID'] = data_header_doc.partner_id.tributes
        data_constants_document['TaxSchemeName'] = tributes[data_header_doc.partner_id.tributes]
        data_constants_document['DocumentCurrencyCode'] = data_header_doc.currency_id.name                                  # Divisa de la Factura
        data_constants_document['CustomerAdditionalAccountID'] = '1' if data_header_doc.partner_id.is_company else '2'
        data_constants_document['CustomerID'] = data_header_doc.partner_id.xidentification if data_header_doc.partner_id.xidentification else '' # Identificador fiscal: En Colombia, el NIT
        data_constants_document['CustomerSchemeID'] = data_header_doc.partner_id.doctype                                    # tipo de identificdor fiscal 
        data_constants_document['CustomerPartyName'] = self._replace_character_especial(data_header_doc.partner_id.name)                                      # Nombre Comercial
        data_constants_document['CustomerDepartment'] = data_header_doc.partner_id.state_id.name if data_header_doc.partner_id.state_id.name else ''
        data_constants_document['CustomerCityCode'] = data_header_doc.partner_id.xcity.code                 # Municipio tabla 6.4.3 res.country.state.city
        data_constants_document['CustomerCityName'] = data_header_doc.partner_id.xcity.name                 # Municipio tabla 6.4.3 res.country.state.city
        data_constants_document['CustomerCountrySubentity'] = data_header_doc.partner_id.state_id.name      # Ciudad o departamento tabla 6.4.2 res.country.state
        data_constants_document['CustomerCountrySubentityCode'] = data_header_doc.partner_id.state_id.code  # Ciudad o departamento tabla 6.4.2 res.country.state
        data_constants_document['CustomerCountryCode'] = data_header_doc.partner_id.country_id.code         # Pa??s tabla 6.4.1 res.country
        data_constants_document['CustomerCountryName'] = data_header_doc.partner_id.country_id.name         # Pa??s tabla 6.4.1 res.country
        data_constants_document['CustomerAddressLine'] = data_header_doc.partner_id.street
        data_constants_document['CustomerTaxLevelCode'] = data_header_doc.partner_id.fiscal_responsability_id.code
        data_constants_document['CustomerRegistrationName'] = self._replace_character_especial(data_header_doc.partner_id.companyName)
        data_constants_document['CustomerEmail'] = data_header_doc.partner_id.email if data_header_doc.partner_id.email else ''
        data_constants_document['CustomerLine'] = data_header_doc.partner_id.street
        data_constants_document['CustomerElectronicMail'] = data_header_doc.partner_id.email
        data_constants_document['CustomerschemeID'] = data_header_doc.partner_id.dv                         # Digito verificador del NIT
        data_constants_document['Firstname'] = self._replace_character_especial(data_header_doc.partner_id.name)

        # falta M??todo de pago Lista de valores 6.3.4.1 (1) - 1 = contado, 2 = Cr??dito
        data_constants_document['PaymentMeansID'] =  '1'  
        # falta C??digo correspondiente al medio de pago Lista de valores 6.3.4.2 (1)
        data_constants_document['PaymentMeansCode'] = '46'
        # falta Fecha de vencimiento de la factura Obligatorio si es venta a cr??dito (0)  
        data_constants_document['PaymentDueDate'] = data_header_doc.date_invoice

        # Datos nota de cr??dito
        if data_constants_document['InvoiceTypeCode'] == '91':
            #invoice_cancel = self.env['account.invoice'].search([('move_name', '=', data_header_doc.origin),('type', '=', 'out_invoice'),('diancode_id', '!=', False)])
            invoice_cancel = self.env['account.invoice'].search([('move_name', '=', data_header_doc.origin),('type', '=', 'out_invoice'),('state_dian_document', '=', 'exitoso')])
            if invoice_cancel:
                dian_document_cancel = self.env['dian.document'].search([('state', '=', 'exitoso'),('document_type', '=', 'f'),('id', '=', invoice_cancel.diancode_id.id)])
                if dian_document_cancel:
                    data_constants_document['IDCancelledBill'] = dian_document_cancel.dian_code
                    data_constants_document['CUFECancelledBill'] = dian_document_cancel.cufe
                    data_constants_document['IssueDateCancelledBill'] = invoice_cancel.date_invoice
        # Genera identificadores ??nico 
        identifier = uuid.uuid4()
        data_constants_document['identifier'] = identifier
        identifierkeyinfo = uuid.uuid4()
        data_constants_document['identifierkeyinfo'] = identifierkeyinfo
        return data_constants_document


    def _replace_character_especial(self, constant):
        if constant:
            constant = constant.replace('&','&amp;')
            constant = constant.replace('<','&lt;')
            constant = constant.replace('>','&gt;')
            constant = constant.replace('"','&quot;')
            constant = constant.replace("'",'&apos;')
        return constant


# <cbc:Note></cbc:Note>
   # <cbc:DocumentCurrencyCode listAgencyID="6" listAgencyName="United Nations Economic Commission for Europe" listID="ISO 4217 Alpha">%(DocumentCurrencyCode)s</cbc:DocumentCurrencyCode>
   # <cac:InvoicePeriod>
   #    <cbc:StartDate>%(InvoicePeriodStartDate)s</cbc:StartDate>
   #    <cbc:EndDate>%(InvoicePeriodEndDate)s</cbc:EndDate>
   # </cac:InvoicePeriod>

      # <cbc:PaymentDueDate>%(PaymentDueDate)s</cbc:PaymentDueDate>
      # <cbc:PaymentID>1234</cbc:PaymentID>

#<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" xmlns:sts="http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures" xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2    http://docs.oasis-open.org/ubl/os-UBL-2.1/xsd/maindoc/UBL-Invoice-2.1.xsd">

    def _template_basic_data_fe_xml(self):
        template_basic_data_fe_xml = """
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" xmlns:sts="http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2    http://docs.oasis-open.org/ubl/os-UBL-2.1/xsd/maindoc/UBL-Invoice-2.1.xsd">
    <ext:UBLExtensions>
        <ext:UBLExtension>
            <ext:ExtensionContent>
                <sts:DianExtensions>
                    <sts:InvoiceControl>
                        <sts:InvoiceAuthorization>%(InvoiceAuthorization)s</sts:InvoiceAuthorization>
                        <sts:AuthorizationPeriod>
                            <cbc:StartDate>%(StartDate)s</cbc:StartDate>
                            <cbc:EndDate>%(EndDate)s</cbc:EndDate>
                        </sts:AuthorizationPeriod>
                        <sts:AuthorizedInvoices>
                            <sts:Prefix>%(Prefix)s</sts:Prefix>
                            <sts:From>%(From)s</sts:From>
                            <sts:To>%(To)s</sts:To>
                        </sts:AuthorizedInvoices>
                    </sts:InvoiceControl>
                    <sts:InvoiceSource>
                        <cbc:IdentificationCode listAgencyID="6" listAgencyName="United Nations Economic Commission for Europe" listSchemeURI="urn:oasis:names:specification:ubl:codelist:gc:CountryIdentificationCode-2.1">%(IdentificationCode)s</cbc:IdentificationCode>
                    </sts:InvoiceSource>
                    <sts:SoftwareProvider>
                        <sts:ProviderID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Direcci??n de Impuestos y Aduanas Nacionales)" schemeID="%(schemeID)s" schemeName="31">%(ProviderID)s</sts:ProviderID>
                        <sts:SoftwareID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Direcci??n de Impuestos y Aduanas Nacionales)">%(SoftwareID)s</sts:SoftwareID>
                    </sts:SoftwareProvider>
                    <sts:SoftwareSecurityCode schemeAgencyID="195" schemeAgencyName="CO, DIAN (Direcci??n de Impuestos y Aduanas Nacionales)">%(SoftwareSecurityCode)s</sts:SoftwareSecurityCode>
                    <sts:AuthorizationProvider>
                        <sts:AuthorizationProviderID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Direcci??n de Impuestos y Aduanas Nacionales)" schemeID="4" schemeName="31">800197268</sts:AuthorizationProviderID>
                    </sts:AuthorizationProvider>
                    <sts:QRCode>URL=https://catalogo-vpfe-hab.dian.gov.co/document/searchqr?documentKey=%(UUID)s</sts:QRCode>
                </sts:DianExtensions>
            </ext:ExtensionContent>
        </ext:UBLExtension>   
        <ext:UBLExtension>
            <ext:ExtensionContent></ext:ExtensionContent>
        </ext:UBLExtension>
    </ext:UBLExtensions>
   <cbc:UBLVersionID>%(UBLVersionID)s</cbc:UBLVersionID>
   <cbc:CustomizationID>%(CustomizationID)s</cbc:CustomizationID>
   <cbc:ProfileID>%(ProfileID)s</cbc:ProfileID>
   <cbc:ProfileExecutionID>%(ProfileExecutionID)s</cbc:ProfileExecutionID>
   <cbc:ID>%(InvoiceID)s</cbc:ID>
   <cbc:UUID schemeID="2" schemeName="CUFE-SHA384">%(UUID)s</cbc:UUID>
   <cbc:IssueDate>%(IssueDate)s</cbc:IssueDate>
   <cbc:IssueTime>%(IssueTime)s</cbc:IssueTime>
   <cbc:InvoiceTypeCode>%(InvoiceTypeCode)s</cbc:InvoiceTypeCode>
   <cbc:DocumentCurrencyCode>%(DocumentCurrencyCode)s</cbc:DocumentCurrencyCode>
   <cbc:LineCountNumeric>%(LineCountNumeric)s</cbc:LineCountNumeric>
   <cac:AccountingSupplierParty>
      <cbc:AdditionalAccountID>%(SupplierAdditionalAccountID)s</cbc:AdditionalAccountID>
      <cac:Party>
         <cac:PartyName>
            <cbc:Name>%(SupplierPartyName)s</cbc:Name>
         </cac:PartyName>
         <cac:PhysicalLocation>
            <cac:Address>
               <cbc:ID>%(SupplierCityCode)s</cbc:ID>
               <cbc:CityName>%(SupplierCityName)s</cbc:CityName>
               <cbc:CountrySubentity>%(SupplierCountrySubentity)s</cbc:CountrySubentity>
               <cbc:CountrySubentityCode>%(SupplierCountrySubentityCode)s</cbc:CountrySubentityCode>
               <cac:AddressLine>
                  <cbc:Line>%(SupplierLine)s</cbc:Line>
               </cac:AddressLine>
               <cac:Country>
                  <cbc:IdentificationCode>%(SupplierCountryCode)s</cbc:IdentificationCode>
                  <cbc:Name languageID="es">%(SupplierCountryName)s</cbc:Name>
               </cac:Country>
            </cac:Address>
         </cac:PhysicalLocation>
         <cac:PartyTaxScheme>
            <cbc:RegistrationName>%(SupplierPartyName)s</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Direcci??n de Impuestos y Aduanas Nacionales)" schemeID="%(schemeID)s" schemeName="31">%(ProviderID)s</cbc:CompanyID>
            <cbc:TaxLevelCode listName="48">%(SupplierTaxLevelCode)s</cbc:TaxLevelCode>
            <cac:RegistrationAddress>
               <cbc:ID>%(SupplierCityCode)s</cbc:ID>
               <cbc:CityName>%(SupplierCityName)s</cbc:CityName>
               <cbc:CountrySubentity>%(SupplierCountrySubentity)s</cbc:CountrySubentity>
               <cbc:CountrySubentityCode>%(SupplierCountrySubentityCode)s</cbc:CountrySubentityCode>
               <cac:AddressLine>
                  <cbc:Line>%(SupplierLine)s</cbc:Line>
               </cac:AddressLine>
               <cac:Country>
                  <cbc:IdentificationCode>%(SupplierCountryCode)s</cbc:IdentificationCode>
                  <cbc:Name languageID="es">%(SupplierCountryName)s</cbc:Name>
               </cac:Country>
            </cac:RegistrationAddress>
            <cac:TaxScheme>
               <cbc:ID>%(TaxSchemeID)s</cbc:ID>
               <cbc:Name>%(TaxSchemeName)s</cbc:Name>
            </cac:TaxScheme>
         </cac:PartyTaxScheme>
         <cac:PartyLegalEntity>
            <cbc:RegistrationName>%(SupplierPartyName)s</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Direcci??n de Impuestos y Aduanas Nacionales)" schemeID="%(schemeID)s" schemeName="31">%(ProviderID)s</cbc:CompanyID>
            <cac:CorporateRegistrationScheme>
               <cbc:ID>%(Prefix)s</cbc:ID>
            </cac:CorporateRegistrationScheme>
         </cac:PartyLegalEntity>
         <cac:Contact>
           <cbc:ElectronicMail>%(SupplierElectronicMail)s</cbc:ElectronicMail>
         </cac:Contact>   
      </cac:Party>
   </cac:AccountingSupplierParty>
   <cac:AccountingCustomerParty>
      <cbc:AdditionalAccountID>%(CustomerAdditionalAccountID)s</cbc:AdditionalAccountID>
      <cac:Party>
         <cac:PartyName>
            <cbc:Name>%(CustomerPartyName)s</cbc:Name>
         </cac:PartyName>
         <cac:PhysicalLocation>
            <cac:Address>
               <cbc:ID>%(CustomerCityCode)s</cbc:ID>
               <cbc:CityName>%(CustomerCityName)s</cbc:CityName>
               <cbc:CountrySubentity>%(CustomerCountrySubentity)s</cbc:CountrySubentity>
               <cbc:CountrySubentityCode>%(CustomerCountrySubentityCode)s</cbc:CountrySubentityCode>
               <cac:AddressLine>
                  <cbc:Line>%(CustomerLine)s</cbc:Line>
               </cac:AddressLine>
               <cac:Country>
                  <cbc:IdentificationCode>%(CustomerCountryCode)s</cbc:IdentificationCode>
                  <cbc:Name languageID="es">%(CustomerCountryName)s</cbc:Name>
               </cac:Country>
            </cac:Address>
         </cac:PhysicalLocation>
         <cac:PartyTaxScheme>
            <cbc:RegistrationName>%(CustomerPartyName)s</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Direcci??n de Impuestos y Aduanas Nacionales)" schemeID="%(CustomerschemeID)s" schemeName="31">%(CustomerID)s</cbc:CompanyID>
            <cbc:TaxLevelCode listName="48">%(CustomerTaxLevelCode)s</cbc:TaxLevelCode>
            <cac:RegistrationAddress>
               <cbc:ID>%(CustomerCityCode)s</cbc:ID>
               <cbc:CityName>%(CustomerCityName)s</cbc:CityName>
               <cbc:CountrySubentity>%(CustomerCountrySubentity)s</cbc:CountrySubentity>
               <cbc:CountrySubentityCode>%(CustomerCountrySubentityCode)s</cbc:CountrySubentityCode>
               <cac:AddressLine>
                  <cbc:Line>%(CustomerLine)s</cbc:Line>
               </cac:AddressLine>
               <cac:Country>
                  <cbc:IdentificationCode>%(CustomerCountryCode)s</cbc:IdentificationCode>
                  <cbc:Name languageID="es">%(CustomerCountryName)s</cbc:Name>
               </cac:Country>
            </cac:RegistrationAddress>
            <cac:TaxScheme>
               <cbc:ID>%(TaxSchemeID)s</cbc:ID>
               <cbc:Name>%(TaxSchemeName)s</cbc:Name>
            </cac:TaxScheme>
         </cac:PartyTaxScheme>
         <cac:PartyLegalEntity>
            <cbc:RegistrationName>%(CustomerPartyName)s</cbc:RegistrationName>
            <cbc:CompanyID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Direcci??n de Impuestos y Aduanas Nacionales)" schemeID="%(CustomerschemeID)s" schemeName="31">%(CustomerID)s</cbc:CompanyID>
        </cac:PartyLegalEntity>
        <cac:Contact>
           <cbc:ElectronicMail>%(CustomerElectronicMail)s</cbc:ElectronicMail>
        </cac:Contact>
        <cac:Person>
           <cbc:FirstName>%(Firstname)s</cbc:FirstName>
        </cac:Person>
      </cac:Party>
   </cac:AccountingCustomerParty>
   <cac:PaymentMeans>
      <cbc:ID>%(PaymentMeansID)s</cbc:ID>
      <cbc:PaymentMeansCode>%(PaymentMeansCode)s</cbc:PaymentMeansCode>
   </cac:PaymentMeans>%(data_taxs_xml)s
   <cac:LegalMonetaryTotal>
      <cbc:LineExtensionAmount currencyID="COP">%(TotalLineExtensionAmount)s</cbc:LineExtensionAmount>
      <cbc:TaxExclusiveAmount currencyID="COP">%(TotalTaxExclusiveAmount)s</cbc:TaxExclusiveAmount>
      <cbc:TaxInclusiveAmount currencyID="COP">%(TotalTaxInclusiveAmount)s</cbc:TaxInclusiveAmount>
      <cbc:PayableAmount currencyID="COP">%(PayableAmount)s</cbc:PayableAmount>
   </cac:LegalMonetaryTotal>%(data_lines_xml)s
</Invoice>
"""
        return template_basic_data_fe_xml

# xmlns:sts="dian:gov:co:facturaelectronica:Structures-2-1"

    def _generate_data_fe_document_xml(self, template_basic_data_fe_xml, dc, dcd, data_taxs_xml, data_lines_xml, CUFE, data_xml_signature):
        template_basic_data_fe_xml = template_basic_data_fe_xml % {'InvoiceAuthorization' : dcd['InvoiceAuthorization'],
            'StartDate' : dcd['StartDate'],
            'EndDate' : dcd['EndDate'],
            'Prefix' : dcd['Prefix'],
            'From' : dcd['From'],
            'To' : dcd['To'],
            'IdentificationCode' : dc['IdentificationCode'],
            'ProviderID' : dc['ProviderID'],
            'SoftwareID' : dc['SoftwareID'],
            'SoftwareSecurityCode' : dc['SoftwareSecurityCode'],
            #'LineExtensionAmount' : dcd['LineExtensionAmount'],
            #'TaxExclusiveAmount' : dcd['TaxExclusiveAmount'],
            'PayableAmount' : dcd['PayableAmount'],
            'UBLVersionID' : dc['UBLVersionID'],
            'ProfileExecutionID' : dc['ProfileExecutionID'],
            'ProfileID' : dc['ProfileID'],
            'CustomizationID' : dc['CustomizationID'],
            'InvoiceID' : dcd['InvoiceID'],
            'UUID' : CUFE,
            'IssueDate' : dcd['IssueDate'],
            'IssueTime' : dcd['IssueTime'],
            'InvoiceTypeCode' : dcd['InvoiceTypeCode'],
            'LineCountNumeric' : dcd['LineCountNumeric'],
            #'InvoicePeriodStartDate' : dcd['InvoicePeriodStartDate'],
            #'InvoicePeriodEndDate' : dcd['InvoicePeriodEndDate'],
            'TaxSchemeID' : dcd['TaxSchemeID'],
            'TaxSchemeName' : dcd['TaxSchemeName'],
            'DocumentCurrencyCode' : dcd['DocumentCurrencyCode'],
            'SupplierAdditionalAccountID' : dc['SupplierAdditionalAccountID'],
            #'SupplierID' : dc['SupplierID'],
            #'SupplierSchemeID' : dc['SupplierSchemeID'],
            'SupplierPartyName' : dc['SupplierPartyName'],
            #'SupplierDepartment' : dc['SupplierDepartment'],
            'SupplierCountrySubentityCode' : dc['SupplierCountrySubentityCode'],
            'SupplierCityName' : dc['SupplierCityName'],
            'SupplierCountrySubentity' : dc['SupplierCountrySubentity'],
            'SupplierLine' : dc['SupplierLine'],
            'SupplierCountryCode' : dc['SupplierCountryCode'],
            'SupplierCountryName' : dc['SupplierCountryName'],
            'SupplierTaxLevelCode' : dc['SupplierTaxLevelCode'],
            #'SupplierRegistrationName' : dc['SupplierRegistrationName'],
            'SupplierCityCode' : dc['SupplierCityCode'],
            'SupplierElectronicMail' : dc['SupplierElectronicMail'],
            'schemeID' : dc['schemeID'],
            'CustomerAdditionalAccountID' : dcd['CustomerAdditionalAccountID'],
            'CustomerID' : dcd['CustomerID'],
            'CustomerSchemeID' : dcd['CustomerSchemeID'],
            'CustomerPartyName' : dcd['CustomerPartyName'],
            #'CustomerDepartment' : dcd['CustomerDepartment'],
            'CustomerCountrySubentityCode' : dcd['CustomerCountrySubentityCode'],
            'CustomerCountrySubentity' : dcd['CustomerCountrySubentity'],
            'CustomerCityName' : dcd['CustomerCityName'],
            'CustomerLine' : dcd['CustomerLine'],
            'CustomerCountryCode' : dcd['CustomerCountryCode'],
            'CustomerCountryName' : dcd['CustomerCountryName'],
            'CustomerTaxLevelCode' : dcd['CustomerTaxLevelCode'],
            #'CustomerEmail' : dcd['CustomerEmail'],                        
            #'CustomerAddressLine' : dcd['CustomerAddressLine'],                                                         
            #'CustomerRegistrationName' : dcd['CustomerRegistrationName'],
            'CustomerschemeID' : dcd['CustomerschemeID'],
            'CustomerCityCode' : dcd['CustomerCityCode'],
            'CustomerElectronicMail' : dcd['CustomerElectronicMail'],
            'TotalLineExtensionAmount' : dcd['LineExtensionAmount'],
            'TotalTaxExclusiveAmount' : dcd['TaxExclusiveAmount'],
            'PaymentMeansID' : dcd['PaymentMeansID'], 
            'PaymentMeansCode' : dcd['PaymentMeansCode'],  
            #'PaymentDueDate' : dcd['PaymentDueDate'],
            'TotalTaxInclusiveAmount' : dcd['TotalTaxInclusiveAmount'],
            'Firstname' : dcd['Firstname'],
            'data_taxs_xml' : data_taxs_xml, 
            'data_lines_xml' : data_lines_xml,  
            }
        return template_basic_data_fe_xml


    def _template_basic_data_nc_xml(self):
        template_basic_data_nc_xml = """
<CreditNote xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" xmlns:clm54217="urn:un:unece:uncefact:codelist:specification:54217:2001" xmlns:clm66411="urn:un:unece:uncefact:codelist:specification:66411:2001" xmlns:clmIANAMIMEMediaType="urn:un:unece:uncefact:codelist:specification:IANAMIMEMediaType:2003" xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" xmlns:qdt="urn:oasis:names:specification:ubl:schema:xsd:QualifiedDatatypes-2" xmlns:sts="http://www.dian.gov.co/contratos/facturaelectronica/v1/Structures" xmlns:udt="urn:un:unece:uncefact:data:specification:UnqualifiedDataTypesSchemaModule:2" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:fe="http://www.dian.gov.co/contratos/facturaelectronica/v1" xsi:schemaLocation="http://www.dian.gov.co/contratos/facturaelectronica/v1 http://factura.today/XSD/r0/DIAN_UBL.xsd">
    <ext:UBLExtensions>
        <ext:UBLExtension>
            <ext:ExtensionContent>
                <sts:DianExtensions>
                    <sts:InvoiceSource>
                        <cbc:IdentificationCode listAgencyID="6" listAgencyName="United Nations Economic Commission for Europe" listSchemeURI="urn:oasis:names:specification:ubl:codelist:gc:CountryIdentificationCode-2.0">CO</cbc:IdentificationCode>
                    </sts:InvoiceSource>
                    <sts:SoftwareProvider>
                        <sts:ProviderID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Direcci??n de Impuestos y Aduanas Nacionales)">%(ProviderID)s</sts:ProviderID>
                        <sts:SoftwareID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Direcci??n de Impuestos y Aduanas Nacionales)">%(SoftwareID)s</sts:SoftwareID>
                    </sts:SoftwareProvider>
                    <sts:SoftwareSecurityCode schemeAgencyID="195" schemeAgencyName="CO, DIAN (Direcci??n de Impuestos y Aduanas Nacionales)">%(SoftwareSecurityCode)s</sts:SoftwareSecurityCode>
                </sts:DianExtensions>
            </ext:ExtensionContent>
        </ext:UBLExtension>
        <ext:UBLExtension>
            <ext:ExtensionContent></ext:ExtensionContent>
        </ext:UBLExtension>
    </ext:UBLExtensions>
    <cbc:UBLVersionID>%(UBLVersionID)s</cbc:UBLVersionID>
    <cbc:CustomizationID/>
    <cbc:ProfileID>%(ProfileID)s</cbc:ProfileID>
    <cbc:ID>%(InvoiceID)s</cbc:ID>
    <cbc:UUID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Direcci??n de Impuestos y Aduanas Nacionales)" schemeURI="http://www.dian.gov.co/contratos/facturaelectronica/v1/anexo_v1_0.pdf#CUFE">%(UUID)s</cbc:UUID>
    <cbc:IssueDate>%(IssueDate)s</cbc:IssueDate>
    <cbc:IssueTime>%(IssueTime)s</cbc:IssueTime>
    <cbc:Note></cbc:Note>
    <cbc:DocumentCurrencyCode>%(DocumentCurrencyCode)s</cbc:DocumentCurrencyCode>
    <AccountingSupplierParty>
        <cbc:AdditionalAccountID>%(SupplierAdditionalAccountID)s</cbc:AdditionalAccountID>
        <Party>
            <cac:PartyIdentification>
                <cbc:ID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Direcci??n de Impuestos y Aduanas Nacionales)" schemeID="%(SupplierSchemeID)s">%(SupplierID)s</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name>%(SupplierPartyName)s</cbc:Name>
            </cac:PartyName>
            <PhysicalLocation>
                <Address>
                    <cbc:Department>%(SupplierDepartment)s</cbc:Department>
                    <cbc:CitySubdivisionName>%(SupplierCityName)s</cbc:CitySubdivisionName>
                    <cbc:CityName>%(SupplierCityName)s</cbc:CityName>
                    <cac:AddressLine>
                        <cbc:Line>%(SupplierLine)s</cbc:Line>
                    </cac:AddressLine>
                    <cac:Country>
                        <cbc:IdentificationCode>%(SupplierCountryCode)s</cbc:IdentificationCode>
                    </cac:Country>
                </Address>
            </PhysicalLocation>
            <PartyTaxScheme>
                <cbc:TaxLevelCode>%(SupplierTaxLevelCode)s</cbc:TaxLevelCode>
                <cac:TaxScheme/>
            </PartyTaxScheme>
            <PartyLegalEntity>
                <cbc:RegistrationName>%(SupplierRegistrationName)s</cbc:RegistrationName>
            </PartyLegalEntity>
        </Party>
    </AccountingSupplierParty>
    <AccountingCustomerParty>
        <cbc:AdditionalAccountID>%(CustomerAdditionalAccountID)s</cbc:AdditionalAccountID>
        <Party>
            <cac:PartyIdentification>
                <cbc:ID schemeAgencyID="195" schemeAgencyName="CO, DIAN (Direcci??n de Impuestos y Aduanas Nacionales)" schemeID="%(CustomerSchemeID)s">%(CustomerID)s</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name>%(CustomerPartyName)s</cbc:Name>
            </cac:PartyName>
            <PhysicalLocation>
                <Address>
                    <cbc:Department>%(CustomerDepartment)s</cbc:Department>
                    <cbc:CitySubdivisionName>%(CustomerCountrySubentity)s</cbc:CitySubdivisionName>
                    <cbc:CityName>%(CustomerCityName)s</cbc:CityName>
                    <cac:AddressLine>
                        <cbc:Line>%(CustomerAddressLine)s</cbc:Line>
                    </cac:AddressLine>
                    <cac:Country>
                        <cbc:IdentificationCode>%(CustomerCountry)s</cbc:IdentificationCode>
                    </cac:Country>
                </Address>
            </PhysicalLocation>
            <PartyTaxScheme>
                <cbc:TaxLevelCode>%(CustomerTaxLevelCode)s</cbc:TaxLevelCode>
                    <cac:TaxScheme/>
            </PartyTaxScheme>
            <PartyLegalEntity>
                <cbc:RegistrationName>%(CustomerRegistrationName)s</cbc:RegistrationName>
            </PartyLegalEntity>
        </Party>
    </AccountingCustomerParty>%(data_taxs_xml)s
    <LegalMonetaryTotal>
        <cbc:LineExtensionAmount currencyID="COP">%(TotalLineExtensionAmount)s</cbc:LineExtensionAmount>
        <cbc:TaxExclusiveAmount currencyID="COP">%(TotalTaxExclusiveAmount)s</cbc:TaxExclusiveAmount>
        <cbc:PayableAmount currencyID="COP">%(PayableAmount)s</cbc:PayableAmount>
    </LegalMonetaryTotal>%(data_credit_lines_xml)s
</CreditNote>"""
        return template_basic_data_nc_xml


    def _generate_data_nc_document_xml(self, template_basic_data_nc_xml, dc, dcd, data_credit_lines_xml, CUFE, data_taxs_xml):
        template_basic_data_nc_xml = template_basic_data_nc_xml % {
                        'ProviderID' : dc['ProviderID'],
                        'SoftwareID' : dc['SoftwareID'],
                        'SoftwareSecurityCode' : dc['SoftwareSecurityCode'],
                        'UBLVersionID' : dc['UBLVersionID'],
                        'ProfileID' : dc['ProfileID'],
                        'InvoiceID' : dcd['InvoiceID'],
                        'UUID' : CUFE,
                        'IssueDate' : dcd['IssueDate'],
                        'IssueTime' : dcd['IssueTime'],
                        'DocumentCurrencyCode' : dcd['DocumentCurrencyCode'],
                        'SupplierAdditionalAccountID' : dc['SupplierAdditionalAccountID'],
                        'SupplierID' : dc['SupplierID'],
                        'SupplierSchemeID' : dc['SupplierSchemeID'],
                        'SupplierPartyName' : dc['SupplierPartyName'],
                        'SupplierDepartment' : dc['SupplierDepartment'],
                        #'SupplierCitySubdivisionName' : dc['SupplierCitySubdivisionName'],
                        'SupplierCityName' : dc['SupplierCityName'],
                        'SupplierLine' : dc['SupplierLine'],
                        'SupplierCountryCode' : dc['SupplierCountryCode'],
                        'SupplierCountryName' : dc['SupplierCountryName'],
                        'SupplierTaxLevelCode' : dc['SupplierTaxLevelCode'],
                        'SupplierRegistrationName' : dc['SupplierRegistrationName'],
                        'CustomerAdditionalAccountID' : dcd['CustomerAdditionalAccountID'],
                        'CustomerID' : dcd['CustomerID'],
                        'CustomerSchemeID' : dcd['CustomerSchemeID'],
                        'CustomerPartyName' : dcd['CustomerPartyName'],
                        'CustomerDepartment' : dcd['CustomerDepartment'],
                        'CustomerCountrySubentity' : dcd['CustomerCountrySubentity'],
                        'CustomerCityName' : dcd['CustomerCityName'],
                        'CustomerAddressLine' : dcd['CustomerAddressLine'], 
                        'CustomerCountry' : dcd['CustomerCountry'],
                        'CustomerRegistrationName' : dcd['CustomerRegistrationName'],
                        'data_taxs_xml' : data_taxs_xml,
                        'TotalLineExtensionAmount' : dcd['LineExtensionAmount'],
                        'TotalTaxExclusiveAmount' : dcd['TaxExclusiveAmount'],
                        'PayableAmount' : dcd['PayableAmount'],                        
                        'data_credit_lines_xml' : data_credit_lines_xml
                        }
        return template_basic_data_nc_xml


    def _template_tax_data_xml(self):
        template_tax_data_xml = """
    <cac:TaxTotal>
        <cbc:TaxAmount currencyID="COP">%(TaxTotalTaxAmount)s</cbc:TaxAmount>
            <cac:TaxSubtotal>
                <cbc:TaxableAmount currencyID="COP">%(TaxTotalTaxableAmount)s</cbc:TaxableAmount>
                <cbc:TaxAmount currencyID="COP">%(TaxTotalTaxAmount)s</cbc:TaxAmount>
                <cac:TaxCategory>
                    <cbc:Percent>%(TaxTotalPercent)s</cbc:Percent>
                    <cac:TaxScheme>
                        <cbc:ID>%(TaxTotalTaxSchemeID)s</cbc:ID>
                        <cbc:Name>%(TaxTotalName)s</cbc:Name>
                    </cac:TaxScheme>
                </cac:TaxCategory>
            </cac:TaxSubtotal>
    </cac:TaxTotal>"""
        return template_tax_data_xml

        # <cbc:FreeOfChargeIndicator>false</cbc:FreeOfChargeIndicator>
        # <cac:TaxTotal>
        #    <cbc:TaxAmount currencyID="COP">%(ILTaxAmount)s</cbc:TaxAmount>
        #    <cac:TaxSubtotal>
        #       <cbc:TaxableAmount currencyID="COP">%(ILTaxableAmount)s</cbc:TaxableAmount>
        #       <cbc:TaxAmount currencyID="COP">%(ILTaxAmount)s</cbc:TaxAmount>
        #       <cac:TaxCategory>
        #          <cbc:Percent>%(ILPercent)s</cbc:Percent>
        #          <cac:TaxScheme>
        #             <cbc:ID>%(ILID)s</cbc:ID>
        #             <cbc:Name>%(ILName)s</cbc:Name>
        #          </cac:TaxScheme>
        #       </cac:TaxCategory>
        #    </cac:TaxSubtotal>
        # </cac:TaxTotal>

                 # <cbc:Percent>%(ILPercent)s</cbc:Percent>

    def _template_line_data_xml(self):
        template_line_data_xml = """
    <cac:InvoiceLine>
        <cbc:ID>%(ILLinea)s</cbc:ID>
        <cbc:InvoicedQuantity unitCode="EA">%(ILInvoicedQuantity)s</cbc:InvoicedQuantity>
        <cbc:LineExtensionAmount currencyID="COP">%(ILLineExtensionAmount)s</cbc:LineExtensionAmount>
        <cbc:FreeOfChargeIndicator>false</cbc:FreeOfChargeIndicator>
        <cac:TaxTotal>
           <cbc:TaxAmount currencyID="COP">%(ILTaxAmount)s</cbc:TaxAmount>
           <cac:TaxSubtotal>
              <cbc:TaxableAmount currencyID="COP">%(ILTaxableAmount)s</cbc:TaxableAmount>
              <cbc:TaxAmount currencyID="COP">%(ILTaxAmount)s</cbc:TaxAmount>
              <cac:TaxCategory>
                 <cbc:Percent>%(ILPercent)s</cbc:Percent>
                 <cac:TaxScheme>
                    <cbc:ID>%(ILID)s</cbc:ID>
                    <cbc:Name>%(ILName)s</cbc:Name>
                 </cac:TaxScheme>
              </cac:TaxCategory>
           </cac:TaxSubtotal>
        </cac:TaxTotal>
        <cac:Item>
            <cbc:Description>%(ILDescription)s</cbc:Description>
             <cac:StandardItemIdentification>
                <cbc:ID schemeAgencyID="10" schemeID="001">18937100-7</cbc:ID>
             </cac:StandardItemIdentification>
        </cac:Item>
        <cac:Price>
            <cbc:PriceAmount currencyID="COP">%(ILPriceAmount)s</cbc:PriceAmount>
            <cbc:BaseQuantity unitCode="NIU">1.000000</cbc:BaseQuantity>
        </cac:Price>
    </cac:InvoiceLine>""" 
        return template_line_data_xml


    def _template_credit_line_data_xml(self):
        template_credit_line_data_xml = """
    <cac:CreditNoteLine>
        <cbc:ID>%(CRLinea)s</cbc:ID>
        <cbc:UUID>%(CUFECancelledBill)s</cbc:UUID> 
        <cbc:LineExtensionAmount currencyID="COP">%(CRLineExtensionAmount)s</cbc:LineExtensionAmount>
        <cac:DiscrepancyResponse>
            <cbc:ReferenceID/>
            <cbc:ResponseCode listName="concepto de notas credito" listSchemeURI="http://www.dian.gov.co/micrositios/fac_electronica/documentos/Anexo_Tecnico_001_Formatos_de_los_Documentos_XML_de_Facturacion_Electron.pdf" name="2:= anulacion de la factura electronica">2</cbc:ResponseCode>
        </cac:DiscrepancyResponse>
        <cac:BillingReference>
            <cac:InvoiceDocumentReference>
                <cbc:ID schemeName="numero de la factura a anular">%(IDCancelledBill)s</cbc:ID>
                <cbc:UUID schemeName="CUFE de la factura de venta || factura de exportacion">%(CUFECancelledBill)s</cbc:UUID>
                <cbc:IssueDate>%(IssueDateCancelledBill)s</cbc:IssueDate>
            </cac:InvoiceDocumentReference> 
            <cac:BillingReferenceLine>
                <cbc:ID/>
                <cbc:Amount currencyID="COP">%(CRLineExtensionAmount)s</cbc:Amount>
            </cac:BillingReferenceLine>
        </cac:BillingReference>
        <cac:TaxTotal>
            <cbc:TaxAmount currencyID="COP">%(CRTaxAmount)s</cbc:TaxAmount>
        </cac:TaxTotal>
        <cac:Item>
            <cbc:Description>%(CRDescription)s</cbc:Description>
        </cac:Item>
    </cac:CreditNoteLine>""" 
        return template_credit_line_data_xml

# Ojo Algorithm 
# Pagina 513 debe existir 3 cert diferentes
#<ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#" Id="xmldsig-%(identifier)s">
#<ds:Reference Id="xmldsig-%(identifier)s-ref0" URI="">
#<ds:Reference URI="#xmldsig-%(identifierkeyinfo)s-keyinfo">

#<ds:SignatureValue Id="xmldsig-%(identifier)s-sigvalue">%(SignatureValue)s</ds:SignatureValue>
#<ds:KeyInfo Id="xmldsig-%(identifierkeyinfo)s-keyinfo">
#<xades:SignedProperties Id="xmldsig-%(identifier)s-signedprops">
#Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"
#Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"

    def _template_signature_data_xml(self):
        template_signature_data_xml = """                               
                <ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#" Id="xmldsig-%(identifier)s">
                    <ds:SignedInfo>
                        <ds:CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>
                        <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
                        <ds:Reference Id="xmldsig-%(identifier)s-ref0" URI="">
                            <ds:Transforms>
                                <ds:Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"/>
                            </ds:Transforms>
                            <ds:DigestMethod  Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>                                             
                            <ds:DigestValue>%(data_xml_signature_ref_zero)s</ds:DigestValue>
                        </ds:Reference>
                        <ds:Reference URI="#xmldsig-%(identifierkeyinfo)s-keyinfo">
                            <ds:DigestMethod  Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                            <ds:DigestValue>%(data_xml_keyinfo_base)s</ds:DigestValue>
                        </ds:Reference>
                        <ds:Reference Type="http://uri.etsi.org/01903#SignedProperties" URI="#xmldsig-%(identifier)s-signedprops">
                            <ds:DigestMethod  Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                            <ds:DigestValue>%(data_xml_SignedProperties_base)s</ds:DigestValue>
                        </ds:Reference>
                    </ds:SignedInfo>
                    <ds:SignatureValue Id="xmldsig-%(identifier)s-sigvalue">%(SignatureValue)s</ds:SignatureValue>
                    <ds:KeyInfo Id="xmldsig-%(identifierkeyinfo)s-keyinfo">
                        <ds:X509Data>
                            <ds:X509Certificate>%(data_public_certificate_base)s</ds:X509Certificate>
                        </ds:X509Data>
                    </ds:KeyInfo>
                    <ds:Object>
                        <xades:QualifyingProperties xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#" Target="#xmldsig-%(identifier)s">
                            <xades:SignedProperties Id="xmldsig-%(identifier)s-signedprops">
                                <xades:SignedSignatureProperties>
                                    <xades:SigningTime>%(data_xml_SigningTime)s</xades:SigningTime>
                                    <xades:SigningCertificate>
                                        <xades:Cert>
                                            <xades:CertDigest>
                                                <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
                                                <ds:DigestValue>%(CertDigestDigestValue)s</ds:DigestValue>
                                            </xades:CertDigest>
                                            <xades:IssuerSerial>
                                                <ds:X509IssuerName>%(IssuerName)s</ds:X509IssuerName>
                                                <ds:X509SerialNumber>%(SerialNumber)s</ds:X509SerialNumber>
                                            </xades:IssuerSerial>
                                        </xades:Cert>
                                    </xades:SigningCertificate>
                                    <xades:SignaturePolicyIdentifier>
                                        <xades:SignaturePolicyId>
                                            <xades:SigPolicyId>
                                                <xades:Identifier>https://facturaelectronica.dian.gov.co/politicadefirma/v2/politicadefirmav2.pdf</xades:Identifier>
                                                <xades:Description>Politica de firma para facturas electronicas de la Republica de Colombia</xades:Description>
                                            </xades:SigPolicyId>
                                            <xades:SigPolicyHash>
                                                <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
                                                <ds:DigestValue>%(data_xml_politics)s</ds:DigestValue>
                                            </xades:SigPolicyHash>
                                        </xades:SignaturePolicyId>
                                    </xades:SignaturePolicyIdentifier>
                                    <xades:SignerRole>
                                        <xades:ClaimedRoles>
                                            <xades:ClaimedRole>supplier</xades:ClaimedRole>
                                        </xades:ClaimedRoles>
                                    </xades:SignerRole>
                                </xades:SignedSignatureProperties>
                            </xades:SignedProperties>
                        </xades:QualifyingProperties>
                    </ds:Object>
                </ds:Signature>""" 
        return template_signature_data_xml 

#<ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
# <xades:QualifyingProperties xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" xmlns:xades141="http://uri.etsi.org/01903/v1.4.1#"

# Original     https://facturaelectronica.dian.gov.co/politicadefirma/v2/politicadefirmav2.pdf
#              Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"
# ejemplo DIAN https://facturaelectronica.dian.gov.co/politicadefirma/v1/politicadefirmav2.pdf
#              Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
               

    def _template_send_data_xml(self):
        template_send_data_xml = """
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:rep="http://www.dian.gov.co/servicios/facturaelectronica/ReportarFactura">
<soapenv:Header>
<wsse:Security soapenv:mustUnderstand="1" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
<wsse:UsernameToken>
<wsse:Username>%(Username)s</wsse:Username>
<wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">%(Password)s</wsse:Password>
<wsse:Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">%(Nonce)s</wsse:Nonce>
<wsu:Created>%(Created)s</wsu:Created>
</wsse:UsernameToken>
</wsse:Security>
</soapenv:Header>
<soapenv:Body>
<rep:EnvioFacturaElectronicaPeticion>
<rep:NIT>%(NIT)s</rep:NIT>
<rep:InvoiceNumber>%(InvoiceNumber)s</rep:InvoiceNumber>
<rep:IssueDate>%(IssueDate)s</rep:IssueDate>
<rep:Document>%(Document)s</rep:Document>
</rep:EnvioFacturaElectronicaPeticion>
</soapenv:Body>
</soapenv:Envelope>"""
        return template_send_data_xml


    @api.model
    def _get_taxs_data(self, invoice_id):
        # ojo ic_04 por inc 04
        dic_taxs_data = {}
        user = self.env['res.users'].search([('id', '=', self.env.uid)])
        company = self.env['res.company'].search([('id', '=', user.company_id.id)])
        iva_01 = 0.00
        ico_04 = 0.00 
        ica_03 = 0.00
        tax_percentage_iva_01 = 0.00
        tax_percentage_ico_04 = 0.00
        tax_percentage_ica_03 = 0.00
        total_base_iva_01 = 0.00
        total_base_ico_04 = 0.00
        total_base_ica_03 = 0.00
        data_tax_detail_doc = self.env['account.invoice.tax'].search([('invoice_id', '=', invoice_id)])

        if data_tax_detail_doc:
            for item_tax in data_tax_detail_doc:
                iva_01 += item_tax.amount if item_tax.tax_id.tax_group_fe == 'iva_fe' else 0.0 
                ica_03 += item_tax.amount if item_tax.tax_id.tax_group_fe == 'ica_fe' else 0.0 
                ico_04 += item_tax.amount if item_tax.tax_id.tax_group_fe == 'ico_fe'  else 0.0
                tax_percentage_iva_01 = self.env['account.tax'].search([('id', '=', item_tax.tax_id.id)]).amount if item_tax.tax_id.tax_group_fe  == 'iva_fe' else tax_percentage_iva_01
                tax_percentage_ica_03 = self.env['account.tax'].search([('id', '=', item_tax.tax_id.id)]).amount if item_tax.tax_id.tax_group_fe  == 'ica_fe' else tax_percentage_ica_03
                tax_percentage_ico_04 = self.env['account.tax'].search([('id', '=', item_tax.tax_id.id)]).amount if item_tax.tax_id.tax_group_fe  == 'ico_fe' else tax_percentage_ico_04
                invoice_lines = self.env['account.invoice.line'].search([('invoice_id', '=', invoice_id), ('invoice_line_tax_ids', 'in', item_tax.tax_id.id)])
                for invoice_line in invoice_lines:
                    total_base_iva_01 += invoice_line.price_subtotal if item_tax.tax_id.tax_group_fe  == 'iva_fe' else 0
                    total_base_ica_03 += invoice_line.price_subtotal if item_tax.tax_id.tax_group_fe  == 'ica_fe' else 0
                    total_base_ico_04 += invoice_line.price_subtotal if item_tax.tax_id.tax_group_fe  == 'ico_fe' else 0

        dic_taxs_data['iva_01'] = self._complements_second_decimal(iva_01)
        dic_taxs_data['tax_percentage_iva_01'] = self._complements_second_decimal(tax_percentage_iva_01)
        dic_taxs_data['total_base_iva_01'] = self._complements_second_decimal(total_base_iva_01)
        dic_taxs_data['ica_03'] = self._complements_second_decimal(ica_03)
        dic_taxs_data['tax_percentage_ica_03'] = self._complements_second_decimal(tax_percentage_ica_03)
        dic_taxs_data['total_base_ica_03'] = self._complements_second_decimal(total_base_ica_03)
        dic_taxs_data['ico_04'] = self._complements_second_decimal(ico_04)
        dic_taxs_data['tax_percentage_ico_04'] = self._complements_second_decimal(tax_percentage_ico_04)
        dic_taxs_data['total_base_ico_04'] = self._complements_second_decimal(total_base_ico_04)
        return dic_taxs_data


    @api.model
    def _generate_taxs_data_xml(self, template_tax_data_xml, data_taxs):
        data_tax_xml = ''
        # iva_01
        TaxTotalTaxAmount = str(data_taxs['iva_01'])                                            # Importe Impuesto (detalle): Importe del impuesto retenido
        TaxTotalTaxEvidenceIndicator = 'false' if data_taxs['iva_01'] == 0.00 else 'true'       # Indica que el elemento es un Impuesto retenido (7.1.1) y no un impuesto (8.1.1) True
        TaxTotalTaxableAmount = str(data_taxs['total_base_iva_01'])                             # 7.1.1.1 / 8.1.1.1 - Base Imponible: Base Imponible sobre la que se calcula la retenci??n de impuesto
        TaxTotalPercent = str(data_taxs['tax_percentage_iva_01'])                               # 7.1.1.3 / 8.1.1.3 - Porcentaje: Porcentaje a aplicar
        TaxTotalTaxSchemeID = '01'                                                              # 7.1.1.2 - Tipo: Tipo o clase impuesto. Concepto fiscal por el que se tributa. Deber??a si un campo que referencia a una lista de c??digos. En la lista deber??an aparecer los impuestos estatales o nacionales. C??digo de impuesto
        TaxTotalName = 'IVA'
        data_tax_xml += template_tax_data_xml % {'TaxTotalTaxAmount' : TaxTotalTaxAmount,
                                                #'TaxTotalTaxEvidenceIndicator' : TaxTotalTaxEvidenceIndicator,
                                                'TaxTotalTaxableAmount' : TaxTotalTaxableAmount,
                                                'TaxTotalPercent' : TaxTotalPercent,
                                                'TaxTotalName' : TaxTotalName,
                                                'TaxTotalTaxSchemeID' : TaxTotalTaxSchemeID,
                                                }
        # ico_04 ojo verificar los impuesto cosidos del os impuesto en odoo
        if data_taxs['ico_04'] != '0.00':
            TaxTotalTaxAmount = str(data_taxs['ico_04'])                                         # Importe Impuesto (detalle): Importe del impuesto retenido
            TaxTotalTaxEvidenceIndicator = 'false' if data_taxs['ico_04'] == 0.00 else 'true'    # Indica que el elemento es un Impuesto retenido (7.1.1) y no un impuesto (8.1.1) True
            TaxTotalTaxableAmount = str(data_taxs['total_base_ico_04'])                          # 7.1.1.1 / 8.1.1.1 - Base Imponible: Base Imponible sobre la que se calcula la retenci??n de impuesto
            TaxTotalPercent = str(data_taxs['tax_percentage_ico_04'])                            # 7.1.1.3 / 8.1.1.3 - Porcentaje: Porcentaje a aplicar
            TaxTotalTaxSchemeID = '04'
            TaxTotalName = 'INC'                                                                 # 7.1.1.2 - Tipo: Tipo o clase impuesto. Concepto fiscal por el que se tributa. Deber??a si un campo que referencia a una lista de c??digos. En la lista deber??an aparecer los impuestos estatales o nacionales. C??digo de impuesto
            data_tax_xml += template_tax_data_xml % {'TaxTotalTaxAmount' : TaxTotalTaxAmount,
                                                    #'TaxTotalTaxEvidenceIndicator' : TaxTotalTaxEvidenceIndicator,
                                                    'TaxTotalTaxableAmount' : TaxTotalTaxableAmount,
                                                    'TaxTotalPercent' : TaxTotalPercent,
                                                    'TaxTotalName' : TaxTotalName,
                                                    'TaxTotalTaxSchemeID' : TaxTotalTaxSchemeID,
                                                    }
        # ica_03
        if data_taxs['ica_03'] != '0.00':
            TaxTotalTaxAmount = str(data_taxs['ica_03'])                                         # Importe Impuesto (detalle): Importe del impuesto retenido
            TaxTotalTaxEvidenceIndicator = 'false' if data_taxs['ica_03'] == 0.00 else 'true'    # Indica que el elemento es un Impuesto retenido (7.1.1) y no un impuesto (8.1.1) True
            TaxTotalTaxableAmount = str(data_taxs['total_base_ica_03'])                          # 7.1.1.1 / 8.1.1.1 - Base Imponible: Base Imponible sobre la que se calcula la retenci??n de impuesto
            TaxTotalPercent = str(data_taxs['tax_percentage_ica_03'])                            # 7.1.1.3 / 8.1.1.3 - Porcentaje: Porcentaje a aplicar
            TaxTotalTaxSchemeID = '03'
            TaxTotalName = 'ICA'                                                                 # 7.1.1.2 - Tipo: Tipo o clase impuesto. Concepto fiscal por el que se tributa. Deber??a si un campo que referencia a una lista de c??digos. En la lista deber??an aparecer los impuestos estatales o nacionales. C??digo de impuesto
            data_tax_xml += template_tax_data_xml % {'TaxTotalTaxAmount' : TaxTotalTaxAmount,
                                                    #'TaxTotalTaxEvidenceIndicator' : TaxTotalTaxEvidenceIndicator,
                                                    'TaxTotalTaxableAmount' : TaxTotalTaxableAmount,
                                                    'TaxTotalPercent' : TaxTotalPercent,
                                                    'TaxTotalName' : TaxTotalName,
                                                    'TaxTotalTaxSchemeID' : TaxTotalTaxSchemeID,
                                                    }

        return data_tax_xml


    def _generate_lines_data_xml(self, template_line_data_xml, invoice_id):
        ILLinea = 0
        data_line_xml = ''
        data_lines_doc = self.env['account.invoice.line'].search([('invoice_id', '=', invoice_id)])
        for data_line in data_lines_doc:
            ILLinea += 1
            ILInvoicedQuantity = self._complements_second_decimal(data_line.quantity)           # 13.1.1.9 - Cantidad: Cantidad del art??culo solicitado. N??mero de unidades servidas/prestadas.
            ILLineExtensionAmount = self._complements_second_decimal(data_line.price_subtotal)  # 13.1.1.12 - Costo Total: Coste Total. Resultado: Unidad de Medida x Precio Unidad.
            ILChargeIndicator = 'true'                                                          # Indica que el elemento es un Cargo (5.1.1) y no un descuento (4.1.1)
            ILAmount =  self._complements_second_decimal(data_line.discount)                    # Valor Descuento: Importe total a descontar.
            ILDescription = self._replace_character_especial(data_line.name)
            ILPriceAmount = self._complements_second_decimal(data_line.price_unit)              # Precio Unitario   
           
            # Valor del tributo
            for line_tax in data_line.invoice_line_tax_ids:
                tax = self.env['account.tax'].search([('id', '=', line_tax.id)])
                ILTaxAmount = self._complements_second_decimal(data_line.price_subtotal * (tax.amount / 100.00))
                ILTaxableAmount = self._complements_second_decimal(data_line.price_subtotal)
                ILPercent  = self._complements_second_decimal(tax.amount)
                ILID = '01' # Falta code dian
                ILName = 'IVA'  #Falta description dian

            data_line_xml += template_line_data_xml % {'ILLinea' : ILLinea,
                                                    'ILInvoicedQuantity' : ILInvoicedQuantity,
                                                    'ILLineExtensionAmount' : ILLineExtensionAmount, # Ojo descuentos mas recargos de la linea
                                                    'ILAmount' : ILAmount,
                                                    'ILDescription' : ILDescription,
                                                    'ILPriceAmount' : ILPriceAmount,
                                                    'ILChargeIndicator' : ILChargeIndicator,
                                                    'ILTaxAmount' : ILTaxAmount,
                                                    'ILTaxableAmount' : ILTaxableAmount,
                                                    'ILPercent' : ILPercent,
                                                    'ILID' : ILID,
                                                    'ILName' : ILName,
                                                    }
        return data_line_xml


    def _generate_credit_lines_data_xml(self , template_credit_line_data_xml, invoice_id, dcd):
        CRLinea = 0
        data_credit_note_line_xml = ''
        data_lines_doc = self.env['account.invoice.line'].search([('invoice_id', '=', invoice_id)])
        for data_line in data_lines_doc:
            CRLinea += 1
            #CRLineExtensionAmount = self._complements_second_decimal(data_line.price_subtotal) # 13.1.1.12 - Costo Total: Coste Total. Resultado: Unidad de Medida x Precio Unidad.
            CRLineExtensionAmount = self._complements_second_decimal(data_line.price_unit)
            CRTaxAmount = self._complements_second_decimal(data_line.price_subtotal - data_line.price_unit)  
            CRDescription = self._replace_character_especial(data_line.name)
            data_credit_note_line_xml += template_credit_line_data_xml % {'CRLinea' : CRLinea,
                                                        'CRLineExtensionAmount' : CRLineExtensionAmount,
                                                        'CUFECancelledBill' : dcd['CUFECancelledBill'],                                                        
                                                        'IDCancelledBill' : dcd['IDCancelledBill'],
                                                        'IssueDateCancelledBill' : dcd['IssueDateCancelledBill'],
                                                        'CRTaxAmount' : CRTaxAmount,
                                                        'CRDescription' : CRDescription,
                                                        }
        return data_credit_note_line_xml


    @api.model
    def _generate_cufe(self, invoice_id, NumFac, FecFac, HoraFac, ValFac, NitOFE, TipAdq, NumAdq, ClTec, ValPag, 
        data_taxs, TipoAmbiente):
        ValFac = str(ValFac)
        CodImp1 = '01' 
        ValImp1 = str(data_taxs['iva_01'])
        CodImp2 = '04'
        ValImp2 = str(data_taxs['ico_04'])
        CodImp3 = '03'
        ValImp3 = str(data_taxs['ica_03'])
        ValPag  = str(ValPag)
        TipAdq  = str(TipAdq)
        CUFE = hashlib.sha384(NumFac+FecFac+HoraFac+ValFac+CodImp1+ValImp1+CodImp2+ValImp2+CodImp3+ValImp3+ValPag+NitOFE+NumAdq+ClTec+TipoAmbiente)
        CUFE = CUFE.hexdigest()
        return CUFE


    def _generate_data_fe_document_xml_signature(self, data_xml_document, data_xml_signature):
        data_xml_document = data_xml_document % {'data_xml_signature' : data_xml_signature,
                        }
        return data_xml_document


    def _generate_data_nc_document_xml_signature(self, data_xml_document, data_xml_signature):
        data_xml_document = data_xml_document % {'data_xml_signature' : data_xml_signature,
                        }
        return data_xml_document

    @api.model
    def _generate_data_send_xml(self, template_send_data_xml, dian_constants, data_constants_document, 
                                Created, Document):
        data_send_xml = template_send_data_xml % {'Username' : dian_constants['Username'],
                        'Password' : dian_constants['Password'],
                        'Nonce' : data_constants_document['Nonce'],
                        'Created' : Created,
                        'NIT' : dian_constants['SupplierID'],
                        'InvoiceNumber' : data_constants_document['InvoiceID'],
                        'IssueDate' : data_constants_document['IssueDateSend'],
                        'Document' : Document,
                        }
        return data_send_xml


    @api.model
    def _generate_signature_ref0(self, data_xml_document, document_repository, password):
        # 1er paso. Generar la referencia 0 que consiste en obtener keyvalue desde todo el xml del 
        #           documento electronico aplicando el algoritmo SHA256 y convirtiendolo a base64
        #template_basic_data_fe_xml = data_xml_document
        #template_basic_data_fe_xml = etree.tostring(etree.fromstring(template_basic_data_fe_xml), method="c14n", exclusive=False,with_comments=False,inclusive_ns_prefixes=None)
        #template_basic_data_fe_xml = etree.tostring(etree.fromstring(template_basic_data_fe_xml), method="c14n")
       
        template_basic_data_fe_xml = data_xml_document
        template_basic_data_fe_xml = etree.tostring(etree.fromstring(template_basic_data_fe_xml), method="c14n", exclusive=False,with_comments=False,inclusive_ns_prefixes=None)
        # print('')
        # print('template_basic_data_fe_xml ', template_basic_data_fe_xml)
        # print('')
        # print(template_basic_data_fe_xmlbbbb)

        data_xml_sha256 = hashlib.new('sha256', template_basic_data_fe_xml)
        data_xml_digest = data_xml_sha256.digest()
        data_xml_signature_ref_zero = base64.b64encode(data_xml_digest)

        #import rsa
        #signature = b64encode(rsa.sign(template_basic_data_fe_xml, private, "SHA-256"))
        
        # archivo_key = document_repository+'/Certificado.p12'
        # try:
        #     key = crypto.load_pkcs12(open(archivo_key, 'rb').read(), password)  
        # except Exception as ex:
        #     raise UserError(tools.ustr(ex))
        # try:
        #     data = crypto.sign(key.get_privatekey(), template_basic_data_fe_xml, 'sha256')               
        # except Exception as ex:
        #     raise UserError(tools.ustr(ex))
        # data_xml_signature_ref_zero = base64.b64encode(data) 
        return data_xml_signature_ref_zero


    @api.model
    def _update_signature(self, template_signature_data_xml, data_xml_signature_ref_zero, data_public_certificate_base, 
                                data_xml_keyinfo_base, data_xml_politics, 
                                data_xml_SignedProperties_base, data_xml_SigningTime, dian_constants,
                                data_xml_SignatureValue, data_constants_document):
        data_xml_signature = template_signature_data_xml % {'data_xml_signature_ref_zero' : data_xml_signature_ref_zero,                                        
                                        'data_public_certificate_base' : data_public_certificate_base,
                                        'data_xml_keyinfo_base' : data_xml_keyinfo_base,
                                        'data_xml_politics' : data_xml_politics,
                                        'data_xml_SignedProperties_base' : data_xml_SignedProperties_base,
                                        'data_xml_SigningTime' : data_xml_SigningTime, 
                                        'CertDigestDigestValue' : dian_constants['CertDigestDigestValue'],
                                        'IssuerName' : dian_constants['IssuerName'], 
                                        'SerialNumber' : dian_constants['SerialNumber'],
                                        'SignatureValue' : data_xml_SignatureValue,
                                        'identifier' : data_constants_document['identifier'],
                                        'identifierkeyinfo' : data_constants_document['identifierkeyinfo'],                                        
                                        }
        return data_xml_signature


    @api.multi
    def _generate_signature_ref1(self, data_xml_keyinfo_generate, document_repository, password):
        # Generar la referencia 1 que consiste en obtener keyvalue desde el keyinfo contenido 
        # en el documento electr??nico aplicando el algoritmo SHA256 y convirtiendolo a base64
        data_xml_keyinfo_generate = etree.tostring(etree.fromstring(data_xml_keyinfo_generate), method="c14n")
        data_xml_keyinfo_sha256 = hashlib.new('sha256', data_xml_keyinfo_generate)
        data_xml_keyinfo_digest = data_xml_keyinfo_sha256.digest()
        data_xml_keyinfo_base = base64.b64encode(data_xml_keyinfo_digest)
        return data_xml_keyinfo_base


    def _generate_digestvalue_to(self, elementTo):
        # Generar el digestvalue de to
        elementTo = etree.tostring(etree.fromstring(elementTo), method="c14n")
        elementTo_sha256 = hashlib.new('sha256', elementTo)
        elementTo_digest = elementTo_sha256.digest()
        elementTo_base = base64.b64encode(elementTo_digest)
        return elementTo_base


    @api.multi
    def _generate_signature_politics(self, document_repository):
        # Generar la referencia 2 que consiste en obtener keyvalue desde el documento de politica 
        # aplicando el algoritmo SHA1 antes del 20 de septimebre de 2016 y sha256 despu??s  de esa 
        # fecha y convirtiendolo a base64. Se  puede utilizar como una constante ya que no variar?? 
        # en a??os segun lo indica la DIAN.
        #  
        # politicav2 = document_repository+'/politicadefirmav2.pdf'
        # politicav2 = open(politicav2,'r')
        # contenido_politicav2 = politicav2.read()
        # politicav2_sha256 = hashlib.new('sha256', contenido_politicav2)
        # politicav2_digest = politicav2_sha256.digest()
        # politicav2_base = base64.b64encode(politicav2_digest)
        # data_xml_politics = politicav2_base
        data_xml_politics = 'dMoMvtcG5aIzgYo0tIsSQeVJBDnUnfSOfBpxXrmor0Y='
        return data_xml_politics


    @api.multi
    def _generate_signature_ref2(self, data_xml_SignedProperties_generate):
        # Generar la referencia 2, se obtine desde el elemento SignedProperties que se 
        # encuentra en la firma aplicando el algoritmo SHA256 y convirtiendolo a base64.
        data_xml_SignedProperties_c14n = etree.tostring(etree.fromstring(data_xml_SignedProperties_generate), method="c14n")
        # print('')
        # print('------------------------------------------------------------------------------------------')
        # print('SignedProperties depues', data_xml_SignedProperties_c14n)
        # print('------------------------------------------------------------------------------------------')
        data_xml_SignedProperties_sha256 = hashlib.new('sha256', data_xml_SignedProperties_c14n)
        data_xml_SignedProperties_digest = data_xml_SignedProperties_sha256.digest()
        data_xml_SignedProperties_base = base64.b64encode(data_xml_SignedProperties_digest)
        return data_xml_SignedProperties_base


    @api.multi
    def _generate_CertDigestDigestValue(self, digital_certificate, password, document_repository):
        #Falta  
        archivo_key = document_repository + '/Certificado.p12'
        key = crypto.load_pkcs12(open(archivo_key, 'rb').read(), password)  
        certificate = hashlib.sha256(crypto.dump_certificate(crypto.FILETYPE_ASN1, key.get_certificate()))
        CertDigestDigestValue = base64.b64encode(certificate.digest())
        return CertDigestDigestValue


    @api.multi
    def _generate_SignatureValue(self, document_repository, password, data_xml_SignedInfo_generate):
        #data_xml_SignatureValue_c14n = etree.tostring(etree.fromstring(data_xml_SignedInfo_generate), method="c14n", exclusive=False, with_comments=False)
        data_xml_SignatureValue_c14n = etree.tostring(etree.fromstring(data_xml_SignedInfo_generate), method="c14n", exclusive=False, with_comments=False)
        # print('')
        # print('------------------------------------------------------------------------------------------')
        # print('Signedinfo despues', data_xml_SignatureValue_c14n)
        # print('Signedinfo despues', data_xml_SignatureValue_c14nFFFFFFF)
        # print('------------------------------------------------------------------------------------------')
        archivo_key = document_repository+'/Certificado.p12'
        try:
            key = crypto.load_pkcs12(open(archivo_key, 'rb').read(), password)  
        except Exception as ex:
            raise UserError(tools.ustr(ex))
        try:
            signature = crypto.sign(key.get_privatekey(), data_xml_SignatureValue_c14n, 'sha256')               
        except Exception as ex:
            raise UserError(tools.ustr(ex))
        SignatureValue = base64.b64encode(signature) 
        archivo_pem = document_repository+'/744524.pem'
        pem = crypto.load_certificate(crypto.FILETYPE_PEM, open(archivo_pem, 'rb').read())
        try:
            validacion = crypto.verify(pem, signature, data_xml_SignatureValue_c14n, 'sha256')
        except:
            raise ValidationError("Firma no fu?? validada exitosamente")

        return SignatureValue


    @api.model
    def _get_doctype(self, doctype):
        if doctype == 'out_invoice':
            docdian = '01'
        elif doctype == 'out_refund':
            docdian = '91'
        else:
            docdian = '92'
        return docdian

    @api.model
    def _get_lines_invoice(self, invoice_id):
        lines = 0
        move_lines = self.env['account.invoice.line'].search([('invoice_id', '=', invoice_id)])
        for move_line in move_lines:
            lines += 1
        return lines


    @api.model
    def _get_date_start_end_invoice(self, invoice_date):
        # Falta
        dates_range_invoice = {}
        dates_range_invoice['InvoicePeriodStartDate'] = '2019-11-01'
        dates_range_invoice['InvoicePeriodEndDate'] = '2019-11-30'
        return dates_range_invoice

        
    @api.model
    def _get_time(self):
        fmt = "%H:%M:%S"
        now_utc = datetime.now(timezone('UTC'))
        now_time = now_utc.strftime(fmt)
        return now_time


    @api.model
    def _get_time_colombia(self):
        fmt = "%H:%M:%S-05:00"
        now_utc = datetime.now(timezone('UTC'))
        now_time = now_utc.strftime(fmt)
        #now_bogota = now_utc.astimezone(timezone('America/Bogota'))
        #now_time = now_bogota.strftime(fmt)
        return now_time

    
    @api.multi
    def _generate_signature_signingtime(self):
        fmt = "%Y-%m-%dT%H:%M:%S"
        now_utc = datetime.now(timezone('UTC'))
        now_bogota = now_utc
        #now_bogota = now_utc.astimezone(timezone('America/Bogota'))
        data_xml_SigningTime = now_bogota.strftime(fmt)+'-05:00'
        return data_xml_SigningTime


    @api.model
    def _generate_xml_filename(self, data_resolution, NitSinDV, doctype):
        if doctype == 'out_invoice':
            docdian = 'face_f'
        elif doctype == 'out_refund':
            docdian = 'face_c'
        else:
            docdian = 'face_d'
        nit = NitSinDV.zfill(10)
        len_prefix = len(data_resolution['Prefix'])
        len_invoice = len(data_resolution['InvoiceID'])
        dian_code_int = int(data_resolution['InvoiceID'][len_prefix:len_invoice])
        dian_code_hex = self.IntToHex(dian_code_int)
        dian_code_hex.zfill(10)
        file_name_xml = docdian + NitSinDV.zfill(10) + dian_code_hex.zfill(10) + '.xml'
        return file_name_xml


    def IntToHex(self, dian_code_int):
        dian_code_hex = '%02x' % dian_code_int
        return dian_code_hex


    def _generate_zip_filename(self, data_resolution, NitSinDV, doctype):
        if doctype == 'out_invoice':
            docdian = 'face_f'
        elif doctype == 'out_refund':
            docdian = 'face_c'
        else:
            docdian = 'face_d'

        nit = NitSinDV.zfill(10)
        len_prefix = len(data_resolution['Prefix'])
        len_invoice = len(data_resolution['InvoiceID'])
        dian_code_int = int(data_resolution['InvoiceID'][len_prefix:len_invoice])
        dian_code_hex = self.IntToHex(dian_code_int)
        dian_code_hex.zfill(10)
        file_name_zip = docdian + NitSinDV.zfill(10) + dian_code_hex.zfill(10) + '.zip'
        return file_name_zip


    def _generate_zip_content(self, FileNameXML, FileNameZIP, data_xml_document, document_repository):
        # Almacena archvio XML
        xml_file = document_repository +'/' + FileNameXML
        f = open (xml_file,'w')
        f.write(data_xml_document)
        f.close()
        # Comprime archvio XML
        zip_file = document_repository + '/' + FileNameZIP
        zf = zipfile.ZipFile(zip_file, mode="w")
        try:
            zf.write(xml_file, compress_type=compression)
        finally:
            zf.close()
        # Obtiene datos comprimidos
        data_xml = zip_file
        data_xml = open(data_xml,'r')
        data_xml = data_xml.read()
        contenido_data_xml_b64 = base64.b64encode(data_xml)
        return contenido_data_xml_b64


    @api.model
    def _generate_barcode(self, dian_constants, data_constants_document, CUFE, data_taxs):
        NumFac = data_constants_document['InvoiceID']
        FecFac = data_constants_document['IssueDateCufe']
        Time = data_constants_document['IssueTime']
        ValFac = data_constants_document['LineExtensionAmount']
        NitOFE = dian_constants['SupplierID']
        DocAdq = data_constants_document['CustomerID']
        ValFacIm = data_constants_document['PayableAmount']
        ValIva = data_taxs['iva_01'] 
        ValOtroIm = data_taxs['ico_04'] + data_taxs['ica_03'] 
        ValTotFac = data_constants_document['TotalTaxInclusiveAmount']  
        datos_qr = ' NumFac: '+NumFac+' FecFac: '+FecFac+' HorFac: '+Time+' NitFac: '+NitOFE+' DocAdq: '+DocAdq+' ValFac: '+str(ValFac)+' ValIva: '+str(ValIva)+' ValOtroIm: '+str(ValOtroIm)+' ValTotFac: '+str(ValTotFac)+' CUFE: '+CUFE
        # Genera c??digo QR
        qr_code = pyqrcode.create(datos_qr)
        qr_code = qr_code.png_as_base64_str(scale=2)
        return qr_code


    @api.model
    def _generate_nonce(self, InvoiceID, seed_code):
        # NonceEncodingType. Se obtiene de:
        # 1. Calcular un valor aleatorio cuya semilla ser?? definida y solamante conocida por el facturador 
        # electr??nico 
        # 2. Convertir a Base 64 el valor aleatorio obtenbido.
        nonce = randint(1,seed_code)
        nonce = base64.b64encode(InvoiceID+str(nonce))
        return nonce


    def _generate_software_security_code(self, software_identification_code, software_pin, NroDocumento):
        software_security_code = hashlib.sha384(software_identification_code + software_pin + NroDocumento)
        software_security_code = software_security_code.hexdigest()
        return  software_security_code 


    def _generate_datetime_timestamp(self):
        fmt = "%Y-%m-%dT%H:%M:%S.%f"
        #now_utc = datetime.now(timezone('UTC'))
        now_bogota = datetime.now(timezone('UTC'))
        #now_bogota = now_utc.astimezone(timezone('America/Bogota'))
        Created = now_bogota.strftime(fmt)[:-3]+'Z'      
        now_bogota = now_bogota + timedelta(minutes=5) 
        Expires = now_bogota.strftime(fmt)[:-3]+'Z'
        timestamp = {'Created' : Created,
            'Expires' : Expires
        }   
        return timestamp


    def _generate_datetime_IssueDate(self):
        date_invoice_cufe = {}
        fmtSend = "%Y-%m-%dT%H:%M:%S"
        now_utc = datetime.now(timezone('UTC'))
        now_bogota = now_utc
        #now_bogota = now_utc.astimezone(timezone('America/Bogota'))
        date_invoice_cufe['IssueDateSend'] = now_bogota.strftime(fmtSend)
        fmtCUFE = "%Y-%m-%d"
        date_invoice_cufe['IssueDateCufe'] = now_bogota.strftime(fmtCUFE)
        fmtInvoice = "%Y-%m-%d"
        date_invoice_cufe['IssueDate'] = now_bogota.strftime(fmtInvoice)
        return date_invoice_cufe


    def _generate_xml_soap_request_validating_dian(self, by_validate_doc, dict_dian_constants):
        UserName = dict_dian_constants['Username']
        Password = dict_dian_constants['Password']
        NitEmisor = dict_dian_constants['NitSinDV']
        IdentificadorSoftware = dict_dian_constants['SoftwareID']
        if by_validate_doc.document_type == 'f':
            TipoDocumento = '1'
        elif by_validate_doc.document_type == 'd':
            TipoDocumento = '2'
        else:
            TipoDocumento = '3'
        NumeroDocumento = by_validate_doc.dian_code
        FechaGeneracion = by_validate_doc.date_document_dian
        CUFE = by_validate_doc.cufe
        template_xml_soap_request_validating_dian = """
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:con="http://www.dian.gov.co/servicios/facturaelectronica/ConsultaDocumentos">
<soapenv:Header>
<wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
<wsse:UsernameToken>
<wsse:Username>%(UserName)s</wsse:Username>
<wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">%(Password)s</wsse:Password>
</wsse:UsernameToken>
</wsse:Security>
</soapenv:Header>
<soapenv:Body>
<con:ConsultaResultadoValidacionDocumentosPeticion>
<con:TipoDocumento>%(TipoDocumento)s</con:TipoDocumento>
<con:NumeroDocumento>%(NumeroDocumento)s</con:NumeroDocumento>
<con:NitEmisor>%(NitEmisor)s</con:NitEmisor>
<con:FechaGeneracion>%(FechaGeneracion)s</con:FechaGeneracion>
<con:IdentificadorSoftware>%(IdentificadorSoftware)s</con:IdentificadorSoftware>
<con:CUFE>%(CUFE)s</con:CUFE>
</con:ConsultaResultadoValidacionDocumentosPeticion>
</soapenv:Body>
</soapenv:Envelope>
"""
        xml_soap_request_validating_dian = template_xml_soap_request_validating_dian % {
                                        'UserName' : UserName,
                                        'Password' : Password,
                                        'TipoDocumento' : TipoDocumento,
                                        'NumeroDocumento' : NumeroDocumento,
                                        'NitEmisor' : NitEmisor,
                                        'FechaGeneracion' : FechaGeneracion,
                                        'IdentificadorSoftware' : IdentificadorSoftware,
                                        'CUFE' : CUFE}
        return xml_soap_request_validating_dian


    def _complements_second_decimal(self, amount):
        amount_dec = ((amount - int(amount)) * 100.0)
        amount_int = int(amount_dec)
        if  amount_int % 10 == 0:
            amount = str(amount) + '0'
        else: 
            amount = str(amount)
        return amount


    def _template_SendTestSetAsyncsend_xml(self):
        template_SendTestSetAsyncsend_xml = """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wcf="http://wcf.dian.colombia">
    <soap:Header xmlns:wsa="http://www.w3.org/2005/08/addressing">
        <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
            <wsu:Timestamp wsu:Id="TS-%(identifier)s">
                <wsu:Created>%(Created)s</wsu:Created>
                <wsu:Expires>%(Expires)s</wsu:Expires>
            </wsu:Timestamp>
            <wsse:BinarySecurityToken EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary" ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3" wsu:Id="BAKENDEVS-%(identifierSecurityToken)s">%(Certificate)s</wsse:BinarySecurityToken>
            <ds:Signature Id="SIG-%(identifier)s" xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
                <ds:SignedInfo>
                    <ds:CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#">
                        <ec:InclusiveNamespaces PrefixList="wsa soap wcf" xmlns:ec="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                    </ds:CanonicalizationMethod>
                    <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
                    <ds:Reference URI="#ID-%(identifierTo)s">
                        <ds:Transforms>
                            <ds:Transform Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#">
                                <ec:InclusiveNamespaces PrefixList="soap wcf" xmlns:ec="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                            </ds:Transform>
                        </ds:Transforms>
                        <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                        <ds:DigestValue></ds:DigestValue>
                    </ds:Reference>
                </ds:SignedInfo>
                <ds:SignatureValue></ds:SignatureValue>
                <ds:KeyInfo Id="KI-%(identifier)s">
                    <wsse:SecurityTokenReference wsu:Id="STR-%(identifier)s">
                        <wsse:Reference URI="#BAKENDEVS-%(identifierSecurityToken)s" ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"/>
                    </wsse:SecurityTokenReference>
                </ds:KeyInfo>
            </ds:Signature>
        </wsse:Security>
        <wsa:Action>http://wcf.dian.colombia/IWcfDianCustomerServices/SendTestSetAsync</wsa:Action>
        <wsa:To wsu:Id="ID-%(identifierTo)s" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc</wsa:To>
    </soap:Header>
    <soap:Body>
        <wcf:SendTestSetAsync>
            <wcf:fileName>%(fileName)s</wcf:fileName>
            <wcf:contentFile>%(contentFile)s</wcf:contentFile>
            <wcf:testSetId>%(testSetId)s</wcf:testSetId>
        </wcf:SendTestSetAsync>
    </soap:Body>
</soap:Envelope>
"""
        return template_SendTestSetAsyncsend_xml


    @api.model
    def _generate_SendTestSetAsync_send_xml(self, template_send_data_xml, fileName, contentFile, Created, 
        testSetId, identifier, Expires, Certificate, identifierSecurityToken, identifierTo):
        data_send_xml = template_send_data_xml % {
                        'fileName' : fileName,
                        'contentFile' : contentFile,
                        'testSetId' : testSetId,
                        'identifier' : identifier,
                        'Created' : Created,
                        'Expires' : Expires,
                        'Certificate' : Certificate,
                        'identifierSecurityToken' : identifierSecurityToken,
                        'identifierTo' : identifierTo,
                        }
        return data_send_xml


    def _template_GetNumberingRange_xml(self):
        template_GetNumberingRange_xml = """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wcf="http://wcf.dian.colombia">
    <soap:Header xmlns:wsa="http://www.w3.org/2005/08/addressing">
        <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
            <wsu:Timestamp wsu:Id="TS-%(identifier)s">
                <wsu:Created>%(Created)s</wsu:Created>
                <wsu:Expires>%(Expires)s</wsu:Expires>
            </wsu:Timestamp>
            <wsse:BinarySecurityToken EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary" ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3" wsu:Id="BAKENDEVS-%(identifierSecurityToken)s">%(Certificate)s</wsse:BinarySecurityToken>
            <ds:Signature Id="SIG-%(identifier)s" xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
                <ds:SignedInfo>
                    <ds:CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#">
                        <ec:InclusiveNamespaces PrefixList="wsa soap wcf" xmlns:ec="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                    </ds:CanonicalizationMethod>
                    <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
                    <ds:Reference URI="#ID-%(identifierTo)s">
                        <ds:Transforms>
                            <ds:Transform Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#">
                                <ec:InclusiveNamespaces PrefixList="soap wcf" xmlns:ec="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                            </ds:Transform>
                        </ds:Transforms>
                        <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                        <ds:DigestValue></ds:DigestValue>
                    </ds:Reference>
                </ds:SignedInfo>
                <ds:SignatureValue></ds:SignatureValue>
                <ds:KeyInfo Id="KI-%(identifier)s">
                    <wsse:SecurityTokenReference wsu:Id="STR-%(identifier)s">
                        <wsse:Reference URI="#BAKENDEVS-%(identifierSecurityToken)s" ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"/>
                    </wsse:SecurityTokenReference>
                </ds:KeyInfo>
            </ds:Signature>
        </wsse:Security>
        <wsa:Action>http://wcf.dian.colombia/IWcfDianCustomerServices/GetNumberingRange</wsa:Action>
        <wsa:To wsu:Id="ID-%(identifierTo)s" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc</wsa:To>
    </soap:Header>
    <soap:Body>
        <wcf:GetNumberingRange>
            <wcf:accountCode>%(accountCode)s</wcf:accountCode>
            <wcf:accountCodeT>%(accountCodeT)s</wcf:accountCodeT>
            <wcf:softwareCode>%(softwareCode)s</wcf:softwareCode>
        </wcf:GetNumberingRange>
    </soap:Body>
</soap:Envelope>
"""
        return template_GetNumberingRange_xml


    @api.model
    def _generate_GetNumberingRange_send_xml(self, template_getstatus_send_data_xml, identifier, Created, 
        Expires,  Certificate, accountCode, accountCodeT, softwareCode, 
        identifierSecurityToken, identifierTo):
        data_consult_numbering_range_send_xml = template_getstatus_send_data_xml % {
                        'identifier' : identifier,
                        'Created' : Created,
                        'Expires' : Expires,
                        'Certificate' : Certificate,
                        'accountCode' : accountCode,
                        'accountCodeT' : accountCodeT,
                        'softwareCode' : softwareCode,
                        'identifierSecurityToken' : identifierSecurityToken,
                        'identifierTo' : identifierTo,
                    }
        return data_consult_numbering_range_send_xml


    def _template_GetStatus_xml(self):
        template_GetStatus_xml = """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:wcf="http://wcf.dian.colombia">
    <soap:Header xmlns:wsa="http://www.w3.org/2005/08/addressing">
        <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
            <wsu:Timestamp wsu:Id="TS-%(identifier)s">
                <wsu:Created>%(Created)s</wsu:Created>
                <wsu:Expires>%(Expires)s</wsu:Expires>
            </wsu:Timestamp>
            <wsse:BinarySecurityToken EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary" ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3" wsu:Id="BAKENDEVS-%(identifierSecurityToken)s">%(Certificate)s</wsse:BinarySecurityToken>
            <ds:Signature Id="SIG-%(identifier)s" xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
                <ds:SignedInfo>
                    <ds:CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#">
                        <ec:InclusiveNamespaces PrefixList="wsa soap wcf" xmlns:ec="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                    </ds:CanonicalizationMethod>
                    <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
                    <ds:Reference URI="#ID-%(identifierTo)s">
                        <ds:Transforms>
                            <ds:Transform Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#">
                                <ec:InclusiveNamespaces PrefixList="soap wcf" xmlns:ec="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                            </ds:Transform>
                        </ds:Transforms>
                        <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                        <ds:DigestValue></ds:DigestValue>
                    </ds:Reference>
                </ds:SignedInfo>
                <ds:SignatureValue></ds:SignatureValue>
                <ds:KeyInfo Id="KI-%(identifier)s">
                    <wsse:SecurityTokenReference wsu:Id="STR-%(identifier)s">
                        <wsse:Reference URI="#BAKENDEVS-%(identifierSecurityToken)s" ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"/>
                    </wsse:SecurityTokenReference>
                </ds:KeyInfo>
            </ds:Signature>
        </wsse:Security>
        <wsa:Action>http://wcf.dian.colombia/IWcfDianCustomerServices/GetStatusZip</wsa:Action>
        <wsa:To wsu:Id="ID-%(identifierTo)s" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc</wsa:To>
    </soap:Header>
    <soap:Body>
        <wcf:GetStatusZip>
            <wcf:trackId>%(trackId)s</wcf:trackId>
        </wcf:GetStatusZip>
    </soap:Body>
</soap:Envelope>
"""
        return template_GetStatus_xml


    @api.model
    def _generate_GetStatus_send_xml(self, template_getstatus_send_data_xml, identifier, Created, Expires,  Certificate, 
        identifierSecurityToken, identifierTo, trackId):
        data_getstatus_send_xml = template_getstatus_send_data_xml % {
                        'identifier' : identifier,
                        'Created' : Created,
                        'Expires' : Expires,
                        'Certificate' : Certificate,
                        'identifierSecurityToken' : identifierSecurityToken,
                        'identifierTo' : identifierTo,
                        'trackId' : trackId,
                    }
        return data_getstatus_send_xml   


    @api.model
    def _generate_GetTaxPayer_send_xml(self, template_getstatus_send_data_xml, identifier, Created, Expires,  Certificate, 
        identifierSecurityToken, identifierTo):
        data_getstatus_send_xml = template_getstatus_send_data_xml % {
                        'identifier' : identifier,
                        'Created' : Created,
                        'Expires' : Expires,
                        'Certificate' : Certificate,
                        'identifierSecurityToken' : identifierSecurityToken,
                        'identifierTo' : identifierTo,
                    }
        return data_getstatus_send_xml  