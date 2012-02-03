import sqlite3

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.utils import DatabaseError, IntegrityError
from django.utils.translation import ugettext_lazy as _

from mutant.contrib.numeric.models import IntegerFieldDefinition
from mutant.contrib.text.models import CharFieldDefinition
from mutant.models.field import FieldDefinitionChoice, NOT_PROVIDED
from mutant.tests.models.utils import BaseModelDefinitionTestCase


class FieldDefinitionInheritanceTest(BaseModelDefinitionTestCase):
    
    @transaction.autocommit
    def test_proxy_inheritance(self):
        obj = CharFieldDefinition.objects.create(name='caca',
                                                  max_length=25,
                                                  model_def=self.model_def)
        save_obj = self.model_def.fielddefinitions.select_subclasses().get()
        self.assertEqual(obj, save_obj)
        
        Model = self.model_def.model_class()
        Model.objects.create(caca="NO WAY")

class FieldDefinitionManipulationTest(BaseModelDefinitionTestCase):
    
    @transaction.autocommit
    def test_field_renaming(self):
        field = CharFieldDefinition.objects.create(name='name',
                                                   max_length=25,
                                                   model_def=self.model_def)
        
        field.name = 'first_name'
        field.save()
        
        Model = self.model_def.model_class()
        msg = "'name' is an invalid keyword argument for this function"
        self.assertRaisesMessage(TypeError, msg,
                                 Model.objects.create, name="Simon")
        
        Model.objects.create(first_name="Julien")
    
    def test_field_alteration(self):
        with transaction.commit_on_success():
            field = CharFieldDefinition.objects.create(name='name',
                                                       max_length=24,
                                                       model_def=self.model_def)
            
        if not isinstance(connection.connection,
                          sqlite3.Connection):
            # sqlite3 doesn't enforce char length
            with transaction.commit_on_success():
                Model = self.model_def.model_class()
                with self.assertRaises(DatabaseError):
                    Model.objects.create(name='Simon' * 5)
        
        with transaction.commit_on_success():
            field.max_length = 25
            field.save()
            Model = self.model_def.model_class()
            Model.objects.create(name='Simon' * 5)
        
        with transaction.commit_on_success():
            field.unique = True
            field.save()
        
        with transaction.commit_on_success():
            Model = self.model_def.model_class()
            Model.objects.create(name='Simon')
            with self.assertRaises(IntegrityError):
                Model.objects.create(name='Simon')
                
        with transaction.commit_on_success():
            field.delete()
            msg = "'name' is an invalid keyword argument for this function"
            self.assertRaisesMessage(TypeError, msg,
                                     Model.objects.create, name="Simon")
                
    def test_field_description(self):
        self.assertEqual(CharFieldDefinition.get_field_description(),
                         _('Char field'))

_incr = 0
def module_level_pickable_default():
    global _incr
    _incr += 1
    return _incr

class FieldDefaultTest(BaseModelDefinitionTestCase):
    
    def test_clean(self):
        field = IntegerFieldDefinition(name='field', model_def=self.model_def)
        
        with self.assertRaises(ValidationError):
            field.default = 'invalid'
            field.clean()
        
        field.default = module_level_pickable_default
        field.clean()
        field.save()
        
        Model = self.model_def.model_class()
        self.assertEqual(Model.objects.create().field, _incr)
        
        field.default = NOT_PROVIDED
        field.save()
        
        with self.assertRaises(ValidationError):
            obj = Model()
            obj.field
            obj.full_clean()
            
class FieldDefinitionChoiceTest(BaseModelDefinitionTestCase):
    
    def test_simple_choices(self):
        field_def = CharFieldDefinition.objects.create(name='gender',
                                                       max_length=1,
                                                       model_def=self.model_def)
        choice = FieldDefinitionChoice(field_def=field_def,
                                       value='Male', label='Male')
        
        self.assertRaises(ValidationError, choice.clean)
        
        choice.value = 'M'
        choice.full_clean()
        choice.save()
        
        Model = self.model_def.model_class()
        obj = Model(gender='Male')
        
        self.assertRaises(ValidationError, obj.full_clean)
        
        FieldDefinitionChoice.objects.create(field_def=field_def,
                                             value='F', label='Female')
        
        obj = Model(gender='F')
        obj.full_clean()

        choices = Model._meta.get_field('gender').get_choices(include_blank=False)
        self.assertEqual(choices, [(u'M', u'Male'), (u'F', u'Female')])
        
    def test_grouped_choices(self):
        field_def = CharFieldDefinition.objects.create(name='media',
                                                       max_length=5,
                                                       model_def=self.model_def)
        
        FieldDefinitionChoice.objects.create(field_def=field_def, group='Audio',
                                             value='vinyl', label='Vinyl')
        FieldDefinitionChoice.objects.create(field_def=field_def, group='Audio',
                                             value='cd', label='CD')
        
        FieldDefinitionChoice.objects.create(field_def=field_def, group='Video',
                                             value='vhs', label='VHS Tape')
        FieldDefinitionChoice.objects.create(field_def=field_def, group='Video',
                                             value='dvd', label='DVD')
        
        FieldDefinitionChoice.objects.create(field_def=field_def,
                                             value='unknown', label='Unknown')
        
        Model = self.model_def.model_class()
        choices = Model._meta.get_field('media').get_choices(include_blank=False)
        expected_choices = [
            ('Audio', (
                    ('vinyl', 'Vinyl'),
                    ('cd', 'CD'),
                )
             ),
            ('Video', (
                    ('vhs', 'VHS Tape'),
                    ('dvd', 'DVD'),
                )
             ),
            ('unknown', 'Unknown')
        ]
        self.assertEqual(choices, expected_choices)
    