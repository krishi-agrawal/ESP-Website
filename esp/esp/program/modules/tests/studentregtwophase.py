__author__    = "Krishi Agrawal <krishi.agrawal26@gmail.com>"
__license__   = "AGPL v.3"

import json
import datetime
from esp.program.tests import ProgramFrameworkTest
from esp.program.modules.base import ProgramModule, ProgramModuleObj
from esp.program.models import ClassSubject, StudentSubjectInterest, StudentRegistration, RegistrationType
from esp.cal.models import Event

class StudentRegTwoPhaseTest(ProgramFrameworkTest):
    def setUp(self):
        super().setUp()
        self.add_user_profiles()
        
        # Get the module object
        self.pm = ProgramModule.objects.get(handler='StudentRegTwoPhase')
        self.moduleobj = ProgramModuleObj.getFromProgModule(self.program, self.pm)
        
        # Pick a student
        self.student = self.students[0]
        self.client.login(username=self.student.username, password='password')
        
        # Get some classes
        self.classes = list(ClassSubject.objects.filter(parent_program=self.program)[:5])
        for cls in self.classes:
            cls.status = 1 # Approved
            cls.save()

    def test_mark_classes_interested(self):
        """Test the mark_classes_interested JSON API."""
        url = '/learn/%s/mark_classes_interested' % self.program.getUrlBase()
        
        interested_ids = [self.classes[0].id, self.classes[1].id]
        not_interested_ids = [self.classes[2].id]
        
        # Initially no interests
        self.assertEqual(StudentSubjectInterest.objects.filter(user=self.student).count(), 0)
        
        # Mark some as interested
        json_data = {
            'interested': interested_ids,
            'not_interested': []
        }
        response = self.client.post(url, {'json_data': json.dumps(json_data)}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        
        self.assertEqual(StudentSubjectInterest.objects.filter(user=self.student, subject__in=interested_ids, end_date=None).count(), 2)
        
        # Mark one as not interested
        json_data = {
            'interested': [],
            'not_interested': [interested_ids[0]]
        }
        response = self.client.post(url, {'json_data': json.dumps(json_data)}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        
        # One should be expired (end_date set)
        self.assertEqual(StudentSubjectInterest.objects.filter(user=self.student, subject=interested_ids[0], end_date__isnull=False).count(), 1)
        self.assertEqual(StudentSubjectInterest.objects.filter(user=self.student, subject=interested_ids[1], end_date=None).count(), 1)

    def test_save_priorities(self):
        """Test the save_priorities JSON API."""
        url = '/learn/%s/save_priorities' % self.program.getUrlBase()
        
        # Ensure we have timeslots
        timeslots = self.program.getTimeSlots(types=['Class Time Block'])
        self.assertTrue(len(timeslots) > 0, "No timeslots found for program")
        timeslot = timeslots[0]
        
        # Ensure we have registration types for priorities
        RegistrationType.objects.get_or_create(name='Priority/1', category='student')
        RegistrationType.objects.get_or_create(name='Priority/2', category='student')
        
        # Assign a class to this timeslot
        cls = self.classes[0]
        sec = cls.get_sections()[0]
        sec.status = 1 # Approved
        sec.save()
        sec.meeting_times.add(timeslot)
        
        # Initially no registrations
        self.assertEqual(StudentRegistration.objects.filter(user=self.student).count(), 0)
        
        # Save priority
        json_data = {
            str(timeslot.id): {
                '1': str(cls.id)
            }
        }
        response = self.client.post(url, {'json_data': json.dumps(json_data)}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 302) # Redirects to core
        
        # Verify registration
        regs = StudentRegistration.objects.filter(user=self.student, section=sec, relationship__name='Priority/1')
        self.assertEqual(regs.count(), 1)
        self.assertTrue(regs[0].is_valid())
        
        # Change priority
        json_data = {
            str(timeslot.id): {
                '1': ''
            }
        }
        response = self.client.post(url, {'json_data': json.dumps(json_data)}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 302)
        
        # Verify expired
        regs = StudentRegistration.objects.filter(user=self.student, section=sec, relationship__name='Priority/1')
        self.assertFalse(regs[0].is_valid())
