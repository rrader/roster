from django.test import TestCase, Client
from django.contrib.auth.models import User
from roster.models import StudentGroup, StudentGroupFeature, WorkplaceUserPlacement
from roster.features import check_group_constraints
import datetime
from django.utils import timezone

class GroupFeatureTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='user1', password='password')
        self.user2 = User.objects.create_user(username='user2', password='password')
        self.user3 = User.objects.create_user(username='user3', password='password')
        
        self.group = StudentGroup.objects.create(name="Test Group")
        self.group.students.add(self.user1, self.user2)
        
        # Enable feature
        StudentGroupFeature.objects.create(
            group=self.group,
            feature_key='non_sequential',
            enabled=True
        )

    def test_check_group_constraints_sequential(self):
        # User 1 sits at computer 5
        WorkplaceUserPlacement.objects.create(
            user=self.user1,
            workplace_id="computer-5"
        )
        
        # User 2 tries to sit at computer 6 (sequential) -> Should fail
        allowed, msg = check_group_constraints(self.user2, "computer-6")
        self.assertFalse(allowed)
        self.assertIn("Щоб зберегти робочий темп уроку", msg)
        
        # User 2 tries to sit at computer 4 (sequential) -> Should fail
        allowed, msg = check_group_constraints(self.user2, "computer-4")
        self.assertFalse(allowed)
        
        # User 2 tries to sit at computer 7 (not sequential) -> Should pass
        allowed, msg = check_group_constraints(self.user2, "computer-7")
        self.assertTrue(allowed)

    def test_check_group_constraints_no_feature(self):
        # Disable feature
        feature = self.group.features.get(feature_key='non_sequential')
        feature.enabled = False
        feature.save()
        
        WorkplaceUserPlacement.objects.create(
            user=self.user1,
            workplace_id="computer-5"
        )
        
        # Should pass even if sequential
        allowed, msg = check_group_constraints(self.user2, "computer-6")
        self.assertTrue(allowed)

    def test_check_group_constraints_different_group(self):
        # User 3 is not in the group
        WorkplaceUserPlacement.objects.create(
            user=self.user1,
            workplace_id="computer-5"
        )
        
        # User 3 tries to sit at computer 6 -> Should pass
        allowed, msg = check_group_constraints(self.user3, "computer-6")
        self.assertTrue(allowed)

    def test_check_group_constraints_time_window(self):
        # User 1 sat at computer 5 a long time ago
        old_time = timezone.now() - datetime.timedelta(hours=3)
        p = WorkplaceUserPlacement.objects.create(
            user=self.user1,
            workplace_id="computer-5"
        )
        p.created_at = old_time
        p.save()
        
        # User 2 tries to sit at computer 6 -> Should pass (old placement)
        allowed, msg = check_group_constraints(self.user2, "computer-6")
        self.assertTrue(allowed)

    def test_check_group_constraints_custom_distance(self):
        # Set min_distance to 2
        feature = self.group.features.get(feature_key='non_sequential')
        feature.parameters = {'min_distance': 2}
        feature.save()
        
        WorkplaceUserPlacement.objects.create(
            user=self.user1,
            workplace_id="computer-5"
        )
        
        # User 2 tries to sit at computer 6 (diff 1) -> Should fail
        allowed, msg = check_group_constraints(self.user2, "computer-6")
        self.assertFalse(allowed)
        
        # User 2 tries to sit at computer 7 (diff 2) -> Should fail
        allowed, msg = check_group_constraints(self.user2, "computer-7")
        self.assertFalse(allowed)
        
        # User 2 tries to sit at computer 8 (diff 3) -> Should pass
        allowed, msg = check_group_constraints(self.user2, "computer-8")
        self.assertTrue(allowed)

    def test_check_group_constraints_error_message(self):
        # User 1 sits at computer 5
        WorkplaceUserPlacement.objects.create(
            user=self.user1,
            workplace_id="computer-5"
        )
        
        # User 2 tries to sit at computer 6 (sequential) -> Should fail
        allowed, msg = check_group_constraints(self.user2, "computer-6")
        self.assertFalse(allowed)
        self.assertIn("Щоб зберегти робочий темп уроку", msg)
        self.assertIn("Ось доступні варіанти для вас", msg)
        
        # Computer 5 is occupied
        # Computer 4 and 6 are forbidden (min_distance=1 default)
        # So 4, 5, 6 should NOT be in the list.
        # 1, 2, 3, 7, 8... should be.
        
        # Check for presence of available computers
        self.assertIn("1, 2, 3, 7, 8", msg)
        
        # Check that forbidden/occupied ones are NOT present
        # We need to be careful not to match "15" as "5".
        # The list is comma separated: "1, 2, 3, 7, 8, ..."
        
        # Split the list part
        list_part = msg.split(":")[-1].strip()
        available_numbers = [int(x.strip()) for x in list_part.split(",")]
        
        self.assertNotIn(4, available_numbers)
        self.assertNotIn(5, available_numbers)
        self.assertNotIn(6, available_numbers)
        self.assertIn(1, available_numbers)
        self.assertIn(7, available_numbers)
